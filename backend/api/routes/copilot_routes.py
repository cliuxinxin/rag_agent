import json
import re
from io import BytesIO
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pypdf import PdfReader
from pydantic import BaseModel, Field

from src.db import (
    STORAGE_DIR,
    add_copilot_message,
    delete_copilot_session,
    get_all_copilot_sessions,
    get_copilot_messages,
    get_copilot_session,
    update_copilot_session_summary_data,
)
from src.graphs.copilot_graph import copilot_chat_graph, copilot_init_graph, load_session_meta
from src.logger import get_logger
from src.nodes.common import get_llm


logger = get_logger("CopilotRoutes")
llm_stream = get_llm().with_config({"streaming": True})
router = APIRouter(tags=["copilot"])


class InitRequest(BaseModel):
    raw_text: str


class ChatRequest(BaseModel):
    session_id: str
    query: Optional[str] = ""
    quote_text: Optional[str] = ""
    quote_anchor: Optional[Dict[str, Any]] = None
    action: str = Field(default="question")


class NotesRequest(BaseModel):
    content: str = ""


def read_text_file(path) -> str:
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def shorten(text: str, limit: int = 120) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def sanitize_filename(text: str, default: str = "reading-copilot") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "-", (text or "")).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:60] or default).strip()


def quote_yaml(text: str) -> str:
    return json.dumps(text or "", ensure_ascii=False)


def normalize_markdown_for_obsidian(text: str) -> str:
    normalized = re.sub(r'<mark class="[^"]+">(.*?)</mark>', r'==\1==', text or "", flags=re.DOTALL)
    return normalized.strip()


def build_callout(title: str, items: list[str], kind: str = "note") -> str:
    cleaned = [item.strip() for item in (items or []) if item and item.strip()]
    if not cleaned:
        return ""
    lines = [f"> [!{kind}] {title}"]
    lines.extend(f"> - {item}" for item in cleaned)
    return "\n".join(lines)


def build_obsidian_markdown(session: Dict[str, Any], markdown_content: str, messages: list[Dict[str, Any]], meta: Dict[str, Any]) -> str:
    summary_data = session.get("summary_data", {}) or {}
    title = session.get("title") or "长文伴读"
    section_summaries = summary_data.get("section_summaries", []) or []
    study_guide = summary_data.get("study_guide", {}) or {}
    argument_map = summary_data.get("argument_map", {}) or {}
    reader_notes = (summary_data.get("reader_notes") or "").strip()
    created_at = session.get("created_at", "")
    note_lines = [
        "---",
        f"title: {quote_yaml(title)}",
        f"created: {quote_yaml(created_at)}",
        f"word_count: {session.get('word_count', 0)}",
        f"read_time: {session.get('read_time', 0)}",
        f"section_count: {len(meta.get('sections', []) or [])}",
        "tags:",
        "  - reading-copilot",
        "  - ai-companion",
        "---",
        "",
        f"# {title}",
        "",
    ]

    summary = (summary_data.get("summary") or "").strip()
    if summary:
        note_lines.extend([
            "> [!summary] 一句话总结",
            f"> {summary}",
            "",
        ])

    takeaways_block = build_callout("核心看点", summary_data.get("takeaways", []), "tip")
    if takeaways_block:
        note_lines.extend([takeaways_block, ""])

    note_lines.append("## 阅读路线")
    note_lines.append("")
    for heading, key in [
        ("开始前先抓", "before_reading"),
        ("阅读时留意", "while_reading"),
        ("读完后检验", "after_reading"),
    ]:
        block = build_callout(heading, study_guide.get(key, []), "note")
        if block:
            note_lines.extend([block, ""])

    if reader_notes:
        note_lines.extend([
            "## 我的笔记",
            "",
            reader_notes,
            "",
        ])

    claims = argument_map.get("claims", []) or []
    tensions = argument_map.get("tensions", []) or []
    if claims or tensions:
        note_lines.extend([
            "## 关键判断",
            "",
        ])
        for index, claim in enumerate(claims, start=1):
            note_lines.extend([
                f"### 判断 {index}",
                "",
                f"- 结论：{claim.get('claim', '').strip()}",
                f"- 依据：{claim.get('evidence', '').strip() or '未提供'}",
            ])
            if claim.get("section_id"):
                note_lines.append(f"- 相关章节：{claim['section_id']}")
            note_lines.append("")
        if tensions:
            tension_block = build_callout("值得再想一层", tensions, "warning")
            if tension_block:
                note_lines.extend([tension_block, ""])

    open_questions = summary_data.get("open_questions", []) or []
    if open_questions:
        note_lines.extend([
            "## 继续深挖",
            "",
        ])
        note_lines.extend(f"- {item}" for item in open_questions if item)
        note_lines.append("")

    if section_summaries:
        note_lines.extend([
            "## 章节陪读",
            "",
        ])
        for section in section_summaries:
            note_lines.extend([
                f"### {section.get('title', '未命名章节')}",
                "",
                f"- 这一节讲了什么：{section.get('summary', '').strip() or '暂无'}",
            ])
            if section.get("role_in_article"):
                note_lines.append(f"- 它在全文里的作用：{section['role_in_article'].strip()}")
            takeaways = [item for item in section.get("takeaways", []) if item]
            if takeaways:
                note_lines.append("- 这一节的关键点：")
                note_lines.extend(f"  - {item}" for item in takeaways)
            if section.get("hidden_assumption"):
                note_lines.append(f"- 隐含前提：{section['hidden_assumption'].strip()}")
            if section.get("question"):
                note_lines.append(f"- 可继续追问：{section['question'].strip()}")
            note_lines.append("")

    if messages:
        note_lines.extend([
            "## 伴读对话",
            "",
        ])
        for message in messages:
            role = "我" if message.get("role") == "user" else "AI 伴读"
            note_lines.append(f"### {role}")
            note_lines.append("")
            if message.get("quote_text"):
                note_lines.append(f"> {message['quote_text'].strip()}")
                note_lines.append("")
            content = (message.get("content") or "").strip()
            if content:
                note_lines.append(content)
                note_lines.append("")

    article_markdown = normalize_markdown_for_obsidian(markdown_content)
    if article_markdown:
        note_lines.extend([
            "## 文章正文",
            "",
            article_markdown,
            "",
        ])

    return "\n".join(note_lines).strip() + "\n"


def update_memory_summary(session_id: str, query: str, answer: str, quote_text: str, references: Optional[list]):
    session = get_copilot_session(session_id) or {}
    summary_data = session.get("summary_data", {}) or {}
    memory = summary_data.get("conversation_memory", {}) or {}

    question_summary = shorten(query or quote_text or "继续追问")
    answer_summary = shorten(answer, 180)
    ref_title = (references or [{}])[0].get("section_title", "全文")
    exchange_line = f"- 围绕《{ref_title}》：用户问“{question_summary}”；助手回答“{answer_summary}”"

    existing_lines = [line for line in (memory.get("summary", "") or "").splitlines() if line.strip()]
    existing_lines.append(exchange_line)
    recent_exchanges = memory.get("recent_exchanges", []) or []
    recent_exchanges.append(f"{ref_title} / {question_summary}")

    summary_data["conversation_memory"] = {
        "summary": "\n".join(existing_lines[-8:]),
        "recent_exchanges": recent_exchanges[-6:],
    }
    update_copilot_session_summary_data(session_id, summary_data)


async def init_copilot_from_text(raw_text: str):
    if not raw_text or len(raw_text.strip()) == 0:
        raise HTTPException(status_code=400, detail="文本不能为空")

    logger.info(f"开始初始化长文伴读，文本长度：{len(raw_text)}")
    result = await copilot_init_graph.ainvoke({"raw_text": raw_text})
    logger.info(f"长文伴读初始化成功，session_id: {result['session_id']}")
    return {"success": True, "session_id": result["session_id"]}


def extract_pdf_text(file_bytes: bytes) -> Dict[str, Any]:
    try:
        reader = PdfReader(BytesIO(file_bytes))
        pages = []
        for index, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            pages.append(text)

        full_text = "\n\n".join(pages).strip()
        return {
            "text": full_text,
            "page_count": len(reader.pages),
            "non_empty_pages": len(pages),
        }
    except Exception as e:
        logger.error(f"PDF 文本提取失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"PDF 解析失败: {str(e)}")


@router.post("/init")
async def init_copilot(request: InitRequest):
    try:
        return await init_copilot_from_text(request.raw_text)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"长文伴读初始化失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")


@router.post("/init_pdf")
async def init_copilot_pdf(file: UploadFile = File(...)):
    try:
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="只支持 PDF 文件")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="PDF 文件为空")

        parsed = extract_pdf_text(content)
        if not parsed["text"]:
            raise HTTPException(status_code=400, detail="PDF 中未提取到可读文本")

        result = await init_copilot_from_text(parsed["text"])
        result["filename"] = filename
        result["page_count"] = parsed["page_count"]
        result["non_empty_pages"] = parsed["non_empty_pages"]
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF 长文伴读初始化失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF 初始化失败: {str(e)}")


@router.get("/sessions")
async def get_sessions():
    try:
        return {"success": True, "data": get_all_copilot_sessions()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    try:
        session = get_copilot_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        md_path = STORAGE_DIR / f"copilot_{session_id}.md"
        raw_path = STORAGE_DIR / f"copilot_{session_id}_raw.txt"
        if not md_path.exists():
            raise HTTPException(status_code=404, detail="文章内容不存在")

        markdown_content = read_text_file(md_path)
        raw_text_content = read_text_file(raw_path)
        messages = get_copilot_messages(session_id)
        meta = load_session_meta(session_id)

        return {
            "success": True,
            "data": {
                **session,
                "markdown_content": markdown_content,
                "raw_text_content": raw_text_content,
                "messages": messages,
                "sections": meta.get("sections", []),
                "chunk_count": len(meta.get("chunks", [])),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话详情失败: {str(e)}")


@router.post("/session/{session_id}/notes")
async def save_session_notes(session_id: str, request: NotesRequest):
    try:
        session = get_copilot_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        summary_data = session.get("summary_data", {}) or {}
        summary_data["reader_notes"] = request.content or ""
        update_copilot_session_summary_data(session_id, summary_data)
        return {"success": True, "data": {"reader_notes": summary_data["reader_notes"]}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存笔记失败: {str(e)}")


@router.get("/session/{session_id}/export_md")
async def export_session_markdown(session_id: str):
    try:
        session = get_copilot_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        md_path = STORAGE_DIR / f"copilot_{session_id}.md"
        if not md_path.exists():
            raise HTTPException(status_code=404, detail="文章内容不存在")

        markdown_content = read_text_file(md_path)
        messages = get_copilot_messages(session_id)
        meta = load_session_meta(session_id)
        payload = build_obsidian_markdown(session, markdown_content, messages, meta)
        filename = sanitize_filename(session.get("title") or "长文伴读") + ".md"

        return Response(
            content=payload,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出 Markdown 失败: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    session = get_copilot_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    async def generate():
        response_content = ""
        references = []
        quote_anchor = request.quote_anchor or {}

        try:
            state = {
                "session_id": request.session_id,
                "user_query": request.query or "",
                "selected_text": request.quote_text or "",
                "quote_anchor": request.quote_anchor or {},
                "action": request.action or "question",
            }
            prepared = await copilot_chat_graph.ainvoke(state)
            references = prepared.get("references", []) or []
            if references and not quote_anchor:
                quote_anchor = references[0]

            add_copilot_message(
                session_id=request.session_id,
                role="user",
                content=request.query or "",
                quote_text=request.quote_text,
                quote_anchor=quote_anchor,
            )

            yield f"data: {json.dumps({'type': 'meta', 'references': references, 'quote_anchor': quote_anchor}, ensure_ascii=False)}\n\n"

            async for chunk in llm_stream.astream(prepared["response_prompt"]):
                content = chunk.content if isinstance(chunk.content, str) else ""
                if not content:
                    continue
                response_content += content
                yield f"data: {json.dumps({'type': 'chunk', 'content': content}, ensure_ascii=False)}\n\n"

            response_content = response_content.strip()
            add_copilot_message(
                session_id=request.session_id,
                role="assistant",
                content=response_content,
                quote_text=request.quote_text,
                quote_anchor=quote_anchor or (references[0] if references else None),
            )
            update_memory_summary(
                session_id=request.session_id,
                query=request.query or "",
                answer=response_content,
                quote_text=request.quote_text or "",
                references=references,
            )

            final_message = {
                "role": "assistant",
                "content": response_content,
                "quote_text": request.quote_text,
                "quote_anchor": quote_anchor or (references[0] if references else None),
                "references": references,
            }
            yield f"data: {json.dumps({'type': 'done', 'message': final_message}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"长文伴读对话失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    try:
        delete_copilot_session(session_id)
        return {"success": True, "message": "删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
