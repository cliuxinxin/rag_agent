import os
import json
import shutil
# [新增] 引入 faiss 读取索引信息
import faiss
from typing import List, Tuple, Any, Dict
from pathlib import Path
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from src.embeddings import HunyuanEmbeddings
from src.logger import get_logger

logger = get_logger("Storage")

STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)

def list_kbs() -> List[str]:
    return [f.stem for f in STORAGE_DIR.glob("*.json")]

def get_kb_details(kb_name: str) -> Dict:
    """
    获取知识库详细信息，新增向量索引健康度检查
    """
    json_path = STORAGE_DIR / f"{kb_name}.json"
    # LangChain 保存 FAISS 时，会在目录下生成 index.faiss 和 index.pkl
    faiss_index_path = STORAGE_DIR / f"{kb_name}_faiss" / "index.faiss"
    
    info = {
        "name": kb_name,
        "doc_count": 0,       # JSON 中的片段数 (应有数量)
        "vector_count": 0,    # FAISS 中的向量数 (实际数量)
        "total_chars": 0,
        "languages": set(),
        "preview": [],
        "health_status": "unknown"  # healthy, corrupted, empty, mismatch
    }
    
    # 1. 读取 JSON (元数据层)
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                info["doc_count"] = len(data)
                for idx, item in enumerate(data):
                    content = item.get("page_content", "")
                    meta = item.get("metadata", {})
                    info["total_chars"] += len(content)
                    if "language" in meta:
                        info["languages"].add(meta["language"])
                    
                    if idx < 3:  # 预览前3条即可
                        info["preview"].append({
                            "content": content[:100] + "..." if len(content) > 100 else content,
                            "source": meta.get("source", "unknown")
                        })
            except Exception as e:
                print(f"JSON读取错误: {e}")

    # 2. 读取 FAISS (物理存储层)
    if faiss_index_path.exists():
        try:
            # 仅读取索引头，速度极快，不需要加载整个模型
            index = faiss.read_index(str(faiss_index_path))
            info["vector_count"] = index.ntotal
            logger.debug(f"知识库 {kb_name}: FAISS 索引读取成功，向量数: {info['vector_count']}")
        except Exception as e:
            logger.error(f"知识库 {kb_name}: FAISS读取错误: {e}")
            info["vector_count"] = -1  # 标记为损坏
    else:
        logger.debug(f"知识库 {kb_name}: FAISS 索引文件不存在")
    
    # 3. 判断健康状态
    if info["doc_count"] == 0 and info["vector_count"] == 0:
        info["health_status"] = "empty"
    elif info["vector_count"] == -1:
        info["health_status"] = "corrupted"  # 索引文件损坏
        logger.warning(f"知识库 {kb_name}: 索引文件损坏")
    elif info["doc_count"] == info["vector_count"]:
        info["health_status"] = "healthy"  # 完美匹配
        logger.info(f"知识库 {kb_name}: 健康状态正常 (JSON: {info['doc_count']}, FAISS: {info['vector_count']})")
    else:
        info["health_status"] = "mismatch"  # 数量不一致 (丢包了)
        loss = info['doc_count'] - info['vector_count']
        logger.warning(f"知识库 {kb_name}: 数据不一致！JSON片段: {info['doc_count']}, FAISS向量: {info['vector_count']}, 丢失: {loss}")
    
    info["languages"] = list(info["languages"])
    return info

def save_kb(kb_name: str, new_docs: List[Document], language: str = "Chinese", progress_bar=None):
    """
    保存知识库，支持进度条回调。
    progress_bar: Streamlit 的进度条对象 (st.progress)
    """
    # 1. JSON 处理
    json_path = STORAGE_DIR / f"{kb_name}.json"
    existing_docs = []
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                for item in data:
                    existing_docs.append(Document(page_content=item["page_content"], metadata=item["metadata"]))
            except: pass
            
    for doc in new_docs:
        doc.metadata["language"] = language
        
    all_docs = existing_docs + new_docs
    
    serialized_data = [{"page_content": d.page_content, "metadata": d.metadata} for d in all_docs]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(serialized_data, f, ensure_ascii=False, indent=2)

    # 2. FAISS 向量处理 (带进度条)
    vector_path = STORAGE_DIR / f"{kb_name}_faiss"
    embeddings = HunyuanEmbeddings() 

    # 定义回调函数更新 UI
    def _update_progress(current, total):
        if progress_bar:
            # 计算百分比 0.0 -> 1.0
            percent = min(current / total, 1.0)
            progress_bar.progress(percent, text=f"正在向量化: {current}/{total}")

    # 提取文本进行向量化
    print(f"开始向量化 {len(new_docs)} 个片段...")
    texts = [d.page_content for d in new_docs]
    metadatas = [d.metadata for d in new_docs]
    
    # 并发生成向量
    raw_embeddings = embeddings.embed_documents(texts, progress_callback=_update_progress)
    
    # === 关键修复：清洗数据 ===
    # 剔除掉那些因为 API 错误变成 None 或 [] 的向量
    valid_text_embeddings = []
    valid_metadatas = []
    
    success_count = 0
    for text, emb, meta in zip(texts, raw_embeddings, metadatas):
        if emb and len(emb) > 0:
            # FAISS 要求格式: (text, embedding_vector)
            valid_text_embeddings.append((text, emb))
            valid_metadatas.append(meta)
            success_count += 1
        else:
            print(f"⚠️ 跳过失败的向量: {text[:20]}...")
            
    if not valid_text_embeddings:
        print("❌ 所有向量化请求均失败，请检查 API Key 或网络。")
        return # 不保存 FAISS，但 JSON 已经保存了，至少 BM25 能用

    print(f"有效向量: {success_count}/{len(texts)}")
    
    # 保存 FAISS
    if vector_path.exists():
        try:
            vectorstore = FAISS.load_local(str(vector_path), embeddings, allow_dangerous_deserialization=True)
            vectorstore.add_embeddings(valid_text_embeddings, valid_metadatas)
        except:
            vectorstore = FAISS.from_embeddings(valid_text_embeddings, embeddings, valid_metadatas)
    else:
        vectorstore = FAISS.from_embeddings(valid_text_embeddings, embeddings, valid_metadatas)
    
    vectorstore.save_local(str(vector_path))

# load_kbs 和 delete_kb 保持不变 (或者复制之前的)
def load_kbs(kb_names: List[str]) -> Tuple[List[Document], Any]:
    all_docs = []
    merged_vectorstore = None
    embeddings = HunyuanEmbeddings()

    for name in kb_names:
        json_path = STORAGE_DIR / f"{name}.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    for item in data:
                        all_docs.append(Document(page_content=item["page_content"], metadata=item["metadata"]))
                except: pass
        
        vector_path = STORAGE_DIR / f"{name}_faiss"
        if vector_path.exists():
            try:
                vs = FAISS.load_local(str(vector_path), embeddings, allow_dangerous_deserialization=True)
                if merged_vectorstore is None:
                    merged_vectorstore = vs
                else:
                    merged_vectorstore.merge_from(vs)
            except: pass
    return all_docs, merged_vectorstore

def delete_kb(kb_name: str):
    json_path = STORAGE_DIR / f"{kb_name}.json"
    if json_path.exists(): os.remove(json_path)
    vector_path = STORAGE_DIR / f"{kb_name}_faiss"
    if vector_path.exists(): shutil.rmtree(vector_path)