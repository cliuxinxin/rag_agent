# src/graphs/copilot_graph.py
from typing import Any, Dict, List, Optional, Tuple
import json
import re

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, StateGraph

from src.db import STORAGE_DIR, create_copilot_session, get_copilot_messages, get_copilot_session
from src.embeddings import HunyuanEmbeddings
from src.nodes.common import get_llm
from src.state import CopilotState


llm = get_llm()
llm_json_mode = get_llm().bind(response_format={"type": "json_object"})


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def make_section_id(index: int, title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title.lower()).strip("-")
    slug = slug[:36] if slug else f"section-{index + 1}"
    return f"section-{index + 1}-{slug}"


def split_markdown_sections(formatted_md: str) -> List[Dict[str, Any]]:
    pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(formatted_md or ""))
    sections: List[Dict[str, Any]] = []

    if not matches:
        body = (formatted_md or "").strip()
        if body:
            sections.append({
                "id": "section-1-body",
                "title": "正文",
                "content": body,
                "markdown": f"## 正文\n\n{body}",
                "word_count": len(strip_html(body)),
            })
        return sections

    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(formatted_md)
        content = formatted_md[start:end].strip()
        section_id = make_section_id(idx, title)
        markdown = f"## {title}\n\n{content}".strip()
        sections.append({
            "id": section_id,
            "title": title,
            "content": content,
            "markdown": markdown,
            "word_count": len(strip_html(content)),
        })

    return sections


def build_chunk_records(sections: List[Dict[str, Any]]) -> Tuple[List[Document], List[Dict[str, Any]]]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=120,
        length_function=len,
    )

    documents: List[Document] = []
    chunks: List[Dict[str, Any]] = []

    for section_index, section in enumerate(sections):
        section_body = strip_html(section.get("content", ""))
        raw_chunks = text_splitter.split_text(section_body) if section_body else [""]
        raw_chunks = [chunk.strip() for chunk in raw_chunks if chunk.strip()]
        if not raw_chunks:
            raw_chunks = [section_body.strip()]

        for chunk_index, chunk_text in enumerate(raw_chunks):
            chunk_id = f"{section['id']}-chunk-{chunk_index + 1}"
            preview = normalize_text(chunk_text)[:140]
            metadata = {
                "chunk_id": chunk_id,
                "section_id": section["id"],
                "section_title": section["title"],
                "section_index": section_index,
                "chunk_index": chunk_index,
                "preview": preview,
            }
            documents.append(
                Document(
                    page_content=f"{section['title']}\n\n{chunk_text}",
                    metadata=metadata,
                )
            )
            chunks.append({
                **metadata,
                "content": chunk_text,
            })

    return documents, chunks


def load_session_meta(session_id: str) -> Dict[str, Any]:
    meta_path = STORAGE_DIR / f"copilot_{session_id}_meta.json"
    if not meta_path.exists():
        return {"sections": [], "chunks": []}

    with open(meta_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {"sections": [], "chunks": []}


def save_session_meta(session_id: str, raw_text: str, formatted_markdown: str, sections: List[Dict[str, Any]], chunks: List[Dict[str, Any]]):
    raw_path = STORAGE_DIR / f"copilot_{session_id}_raw.txt"
    markdown_path = STORAGE_DIR / f"copilot_{session_id}.md"
    meta_path = STORAGE_DIR / f"copilot_{session_id}_meta.json"

    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_text or "")

    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(formatted_markdown or "")

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"sections": sections, "chunks": chunks}, f, ensure_ascii=False, indent=2)


def extract_references_from_docs(docs: List[Document]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    seen = set()
    for doc in docs:
        meta = doc.metadata or {}
        chunk_id = meta.get("chunk_id")
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        refs.append({
            "chunk_id": chunk_id,
            "section_id": meta.get("section_id"),
            "section_title": meta.get("section_title"),
            "preview": meta.get("preview", normalize_text(doc.page_content)[:140]),
        })
    return refs


def find_chunk_for_quote(chunks: List[Dict[str, Any]], selected_text: str, quote_anchor: Optional[Dict[str, Any]]) -> Optional[int]:
    if quote_anchor:
        chunk_id = quote_anchor.get("chunk_id")
        section_id = quote_anchor.get("section_id")
        for idx, chunk in enumerate(chunks):
            if chunk_id and chunk.get("chunk_id") == chunk_id:
                return idx
            if section_id and chunk.get("section_id") == section_id:
                return idx

    target = normalize_text(strip_html(selected_text))
    if not target:
        return None

    for idx, chunk in enumerate(chunks):
        normalized_chunk = normalize_text(chunk.get("content", ""))
        if target and target in normalized_chunk:
            return idx

    # Fallback: choose the chunk with the highest substring overlap.
    best_idx = None
    best_score = 0
    for idx, chunk in enumerate(chunks):
        normalized_chunk = normalize_text(chunk.get("content", ""))
        overlap = len(set(target.split()) & set(normalized_chunk.split()))
        if overlap > best_score:
            best_score = overlap
            best_idx = idx
    return best_idx


def build_quote_context(chunks: List[Dict[str, Any]], target_idx: int, selected_text: str) -> Tuple[str, List[Dict[str, Any]]]:
    indexes = [idx for idx in [target_idx - 1, target_idx, target_idx + 1] if 0 <= idx < len(chunks)]
    refs = []
    blocks = [f"选中原文：{selected_text.strip()}"]

    for idx in indexes:
        chunk = chunks[idx]
        refs.append({
            "chunk_id": chunk["chunk_id"],
            "section_id": chunk["section_id"],
            "section_title": chunk["section_title"],
            "preview": chunk["preview"],
        })
        blocks.append(
            f"[{chunk['section_title']} / 段落 {chunk['chunk_index'] + 1}]\n{chunk['content']}"
        )

    return "\n\n".join(blocks), refs


def build_search_context(session_id: str, query: str) -> Tuple[str, List[Dict[str, Any]]]:
    embeddings = HunyuanEmbeddings()
    faiss_path = STORAGE_DIR / f"copilot_{session_id}_faiss"
    vector_store = FAISS.load_local(str(faiss_path), embeddings, allow_dangerous_deserialization=True)
    docs = vector_store.similarity_search(query, k=4)
    refs = extract_references_from_docs(docs)
    context_blocks = []
    for doc in docs:
        meta = doc.metadata or {}
        title = meta.get("section_title") or "相关段落"
        body = doc.page_content.split("\n\n", 1)[-1]
        context_blocks.append(f"[{title}]\n{body}")
    return "\n\n".join(context_blocks), refs


def build_memory_context(session_id: str) -> str:
    session = get_copilot_session(session_id) or {}
    summary_data = session.get("summary_data", {}) or {}
    memory = summary_data.get("conversation_memory", {}) or {}
    pieces: List[str] = []

    if memory.get("summary"):
        pieces.append("历史对话记忆：")
        pieces.append(memory["summary"])

    recent_exchanges = memory.get("recent_exchanges", []) or []
    if recent_exchanges:
        pieces.append("最近几轮关注点：")
        pieces.extend(f"- {item}" for item in recent_exchanges[-4:])

    recent_messages = get_copilot_messages(session_id)[-6:]
    if recent_messages:
        pieces.append("最近消息摘录：")
        for message in recent_messages:
            role = "用户" if message.get("role") == "user" else "助手"
            content = normalize_text(message.get("content", ""))[:140]
            if content:
                pieces.append(f"- {role}：{content}")

    return "\n".join(pieces).strip()


def build_response_prompt(
    action: str,
    context: str,
    user_query: str,
    selected_text: str,
    memory_context: str,
    references: List[Dict[str, Any]],
    article_snapshot: Dict[str, Any],
) -> str:
    summary = article_snapshot.get("summary", "")
    takeaways = article_snapshot.get("takeaways", []) or []
    takeaway_text = "\n".join(f"- {item}" for item in takeaways[:4]) if takeaways else "- 暂无"
    reference_text = "\n".join(
        f"- {ref.get('section_title', '相关段落')}（{ref.get('preview', '')}）"
        for ref in references[:3]
    ) or "- 暂无"

    action_instruction_map = {
        "explain": "请解释选中内容的真实含义，先讲一句话结论，再拆概念、逻辑和上下文，最后说明它在全文里的作用。",
        "translate": "请把选中内容翻译成更自然的中文，并补一句它在全文里的作用。",
        "summarize": "请总结这段内容，输出 1 句摘要 + 3 个要点。",
        "question": "请基于上下文回答用户问题。先直接回答，再说明它与全文主线的关系，最后给出 1 个建议继续追问或继续阅读的方向。如果上下文不足，请明确说还缺什么信息。",
        "explain_5yr": "请像给 5 岁小朋友讲故事一样解释，但不要牺牲原意。",
        "extract_quote": "请提炼一句不超过 30 字的金句，并用一句话解释它为什么重要。",
        "feynman_quiz": "请提出 1 个真正能暴露理解深浅的挑战问题，只输出问题本身。",
    }
    action_instruction = action_instruction_map.get(action, action_instruction_map["question"])

    selected_block = f"用户重点选中的原文：{selected_text}" if selected_text else "用户没有选中具体原文。"
    question_block = f"用户问题：{user_query}" if user_query else "用户没有额外补充问题。"

    return f"""
你是一个真正会陪用户读长文的 AI 助教。

你的回答规则：
1. 只能基于给定原文上下文回答，不要编造文中不存在的事实。
2. 如果是在解释局部段落，要结合上下文说明它在全文里的作用。
3. 回答尽量清晰、具体，优先帮助用户读懂，而不是写空泛套话。
4. 若上下文不够，请直接说“仅根据当前片段我还不能确定”，并指出还需要哪部分原文。
5. 如果合适，可以自然点出参考小节标题，但不要伪造引用。

当前文章总览：
- 全文总结：{summary or '暂无'}
- 核心看点：
{takeaway_text}

本轮可参考的段落：
{reference_text}

{selected_block}

{question_block}

对话记忆：
{memory_context or '暂无历史记忆'}

原文上下文：
{context}

本轮任务：
{action_instruction}
""".strip()


def ensure_summary_defaults(summary_data: Dict[str, Any], sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary_data = summary_data or {}
    summary_data.setdefault("summary", "这篇文章的导读暂时生成失败。")
    summary_data.setdefault("takeaways", [])
    summary_data.setdefault("section_summaries", [])
    summary_data.setdefault("study_guide", {
        "before_reading": [],
        "while_reading": [],
        "after_reading": [],
    })
    summary_data.setdefault("podcast_script", [])
    summary_data.setdefault("knowledge_graph", {"nodes": [], "edges": []})
    summary_data.setdefault("argument_map", {"claims": [], "tensions": []})
    summary_data.setdefault("open_questions", [])
    summary_data.setdefault("conversation_memory", {"summary": "", "recent_exchanges": []})
    summary_data.setdefault("reader_notes", "")
    summary_data["sections"] = [
        {
            "id": section["id"],
            "title": section["title"],
            "word_count": section["word_count"],
        }
        for section in sections
    ]
    return summary_data


def text_formatter_node(state: CopilotState) -> CopilotState:
    raw_text = state["raw_text"]

    prompt = f"""
你是专业的文本排版师，请将下面的无格式长文本进行优化排版，输出 Markdown 格式。

要求：
1. 修复断行和不合理的换行，将零散的句子合并成连贯段落。
2. 每隔约 800 字根据语义插入一个 `##` 二级标题，标题要能概括该部分内容。
3. 保持原文内容不丢失、不改意、不补写事实。
4. 不要添加一级标题。
5. 对文中重要信息使用 HTML 标记，不要改成 Markdown 粗体：
   - 重要数据、金额、百分比：`<mark class="lens-data">内容</mark>`
   - 核心人名、机构、专有名词、重要概念：`<mark class="lens-entity">内容</mark>`
   - 逻辑转折词或结论词：`<mark class="lens-logic">内容</mark>`
6. 除 `mark` 外，不要额外引入别的 HTML 标签。

原始文本：
{raw_text}
"""

    response = llm.invoke(prompt)
    formatted_md = response.content.strip()
    return {"formatted_markdown": formatted_md}


def structure_builder_node(state: CopilotState) -> CopilotState:
    sections = split_markdown_sections(state["formatted_markdown"])
    _, chunks = build_chunk_records(sections)
    return {"sections": sections, "chunks": chunks}


def summarizer_node(state: CopilotState) -> CopilotState:
    sections = state.get("sections", [])
    if not sections:
        return {
            "summary_data": ensure_summary_defaults({}, [])
        }

    section_summaries = []
    for section in sections:
        prompt = f"""
请阅读下面这个章节，并输出严格 JSON：
{{
  "summary": "用 1 句话概括这一节",
  "role_in_article": "这一节在全文里的作用",
  "takeaways": ["要点1", "要点2"],
  "question": "读完这一节后最值得追问的 1 个问题",
  "hidden_assumption": "这一节默认成立但未明说的前提"
}}

章节标题：{section['title']}
章节内容：
{section['markdown'][:4000]}
"""
        try:
            response = llm_json_mode.invoke(prompt)
            payload = json.loads(response.content.strip())
        except Exception:
            payload = {
                "summary": f"{section['title']} 的摘要生成失败。",
                "role_in_article": "",
                "takeaways": [],
                "question": "",
                "hidden_assumption": "",
            }

        section_summaries.append({
            "id": section["id"],
            "title": section["title"],
            "word_count": section["word_count"],
            "summary": payload.get("summary", ""),
            "role_in_article": payload.get("role_in_article", ""),
            "takeaways": payload.get("takeaways", [])[:3],
            "question": payload.get("question", ""),
            "hidden_assumption": payload.get("hidden_assumption", ""),
        })

    digest_text = "\n\n".join(
        [
            f"章节：{item['title']}\n"
            f"摘要：{item['summary']}\n"
            f"作用：{item['role_in_article'] or '无'}\n"
            f"要点：{'；'.join(item['takeaways']) or '无'}\n"
            f"追问：{item['question'] or '无'}\n"
            f"隐含前提：{item['hidden_assumption'] or '无'}"
            for item in section_summaries
        ]
    )

    aggregate_prompt = f"""
请基于下面的章节摘要，生成一份适合“长文伴读”的严格 JSON：
{{
  "summary": "一句话总结全文",
  "takeaways": ["核心看点1", "核心看点2", "核心看点3"],
  "study_guide": {{
    "before_reading": ["开始读之前先抓什么"],
    "while_reading": ["阅读时要特别留意什么"],
    "after_reading": ["读完后如何检验自己是否真的读懂"]
  }},
  "podcast_script": [
    {{"speaker": "A", "text": "..." }},
    {{"speaker": "B", "text": "..." }}
  ],
  "knowledge_graph": {{
    "nodes": [{{"id": 1, "name": "概念", "category": "核心概念"}}],
    "edges": [{{"source": 1, "target": 2, "label": "关系"}}]
  }},
  "argument_map": {{
    "claims": [
      {{"claim": "文章的重要判断", "evidence": "支撑它的依据", "section_id": "相关章节 id"}}
    ],
    "tensions": ["文中存在张力或值得怀疑的地方"]
  }},
  "open_questions": ["读完全文后值得继续深挖的问题1", "问题2"]
}}

要求：
1. 要覆盖全文，而不是只看开头。
2. `section_id` 只能从给定章节里选择。
3. `takeaways` 以用户能继续阅读下去为目标，不要写成空话。
4. `study_guide` 要写得像真正的阅读路线，而不是泛泛的鸡汤。

章节摘要：
{digest_text}

可用章节：
{json.dumps([{"id": sec["id"], "title": sec["title"]} for sec in sections], ensure_ascii=False)}
"""

    try:
        response = llm_json_mode.invoke(aggregate_prompt)
        summary_data = json.loads(response.content.strip())
    except Exception:
        summary_data = {}

    summary_data["section_summaries"] = section_summaries
    summary_data = ensure_summary_defaults(summary_data, sections)
    return {"summary_data": summary_data}


def metadata_calc_node(state: CopilotState) -> CopilotState:
    formatted_md = state["formatted_markdown"]
    text = strip_html(re.sub(r"[#*_`~]", "", formatted_md))
    word_count = len(text)
    read_time = max(1, round(word_count / 400))
    return {"word_count": word_count, "read_time": read_time}


def save_session_node(state: CopilotState) -> CopilotState:
    summary_data = state["summary_data"]
    word_count = state["word_count"]
    read_time = state["read_time"]
    sections = state.get("sections", [])

    title = summary_data.get("summary", "")
    if not title and sections:
        title = sections[0]["title"]
    title = title[:30] + "..." if len(title) > 30 else title

    session_id = create_copilot_session(
        title=title or "长文伴读",
        word_count=word_count,
        read_time=read_time,
        summary_data=summary_data,
    )
    return {"session_id": session_id}


def vector_store_builder_node(state: CopilotState) -> CopilotState:
    formatted_md = state["formatted_markdown"]
    session_id = state["session_id"]
    raw_text = state["raw_text"]
    sections = state.get("sections", [])
    chunks = state.get("chunks", [])

    documents = [
        Document(
            page_content=f"{chunk['section_title']}\n\n{chunk['content']}",
            metadata={
                "chunk_id": chunk["chunk_id"],
                "section_id": chunk["section_id"],
                "section_title": chunk["section_title"],
                "section_index": chunk["section_index"],
                "chunk_index": chunk["chunk_index"],
                "preview": chunk["preview"],
            },
        )
        for chunk in chunks
    ]

    embeddings = HunyuanEmbeddings()
    vector_store = FAISS.from_documents(documents, embeddings)
    faiss_path = STORAGE_DIR / f"copilot_{session_id}_faiss"
    vector_store.save_local(str(faiss_path))

    save_session_meta(session_id, raw_text, formatted_md, sections, chunks)
    return {"vector_store": vector_store}


def context_router_node(state: CopilotState) -> CopilotState:
    selected_text = state.get("selected_text", "") or ""
    quote_anchor = state.get("quote_anchor") or {}
    session_id = state["session_id"]
    user_query = state.get("user_query", "") or ""
    meta = load_session_meta(session_id)
    chunks = meta.get("chunks", [])

    if selected_text.strip():
        target_idx = find_chunk_for_quote(chunks, selected_text, quote_anchor)
        if target_idx is not None:
            context, refs = build_quote_context(chunks, target_idx, selected_text)
            return {"context": context, "references": refs}

    context, refs = build_search_context(session_id, user_query or selected_text)
    return {"context": context, "references": refs}


def memory_builder_node(state: CopilotState) -> CopilotState:
    return {"memory_context": build_memory_context(state["session_id"])}


def prompt_builder_node(state: CopilotState) -> CopilotState:
    session = get_copilot_session(state["session_id"]) or {}
    summary_data = session.get("summary_data", {}) or {}
    prompt = build_response_prompt(
        action=state["action"],
        context=state["context"],
        user_query=state.get("user_query", ""),
        selected_text=state.get("selected_text", ""),
        memory_context=state.get("memory_context", ""),
        references=state.get("references", []),
        article_snapshot=summary_data,
    )
    return {"response_prompt": prompt}


def build_copilot_init_graph():
    workflow = StateGraph(CopilotState)
    workflow.add_node("TextFormatter", text_formatter_node)
    workflow.add_node("StructureBuilder", structure_builder_node)
    workflow.add_node("Summarizer", summarizer_node)
    workflow.add_node("MetadataCalc", metadata_calc_node)
    workflow.add_node("SaveSession", save_session_node)
    workflow.add_node("VectorStoreBuilder", vector_store_builder_node)

    workflow.set_entry_point("TextFormatter")
    workflow.add_edge("TextFormatter", "StructureBuilder")
    workflow.add_edge("StructureBuilder", "Summarizer")
    workflow.add_edge("Summarizer", "MetadataCalc")
    workflow.add_edge("MetadataCalc", "SaveSession")
    workflow.add_edge("SaveSession", "VectorStoreBuilder")
    workflow.add_edge("VectorStoreBuilder", END)
    return workflow.compile()


def build_copilot_chat_graph():
    workflow = StateGraph(CopilotState)
    workflow.add_node("ContextRouter", context_router_node)
    workflow.add_node("MemoryBuilder", memory_builder_node)
    workflow.add_node("PromptBuilder", prompt_builder_node)

    workflow.set_entry_point("ContextRouter")
    workflow.add_edge("ContextRouter", "MemoryBuilder")
    workflow.add_edge("MemoryBuilder", "PromptBuilder")
    workflow.add_edge("PromptBuilder", END)
    return workflow.compile()


copilot_init_graph = build_copilot_init_graph()
copilot_chat_graph = build_copilot_chat_graph()
