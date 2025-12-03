import sqlite3
import uuid
import json  # 新增
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


# === 修改核心：将路径指向 storage 目录 ===
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True) # 确保目录存在
DB_PATH = STORAGE_DIR / "chat_history.db"

def init_db():
    """初始化数据库表结构"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    # 会话表
    c.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 消息表
    c.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )
    ''')

    # === 新增：深度解读报告表 ===
    c.execute('''
    CREATE TABLE IF NOT EXISTS research_reports (
        id TEXT PRIMARY KEY,
        title TEXT,
        source_name TEXT, -- 文件名或 "Text Input"
        content TEXT,     -- 最终的 Markdown 报告
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # === [新增] 会话附带的上下文数据表 ===
    # 用于存储深度问答模式下的：文档全文、文档标题、以及 Agent 的推理历史
    c.execute('''
    CREATE TABLE IF NOT EXISTS session_artifacts (
        session_id TEXT PRIMARY KEY,
        doc_title TEXT,
        doc_content TEXT,  -- 存储文档全文
        qa_pairs TEXT,     -- 存储 JSON 格式的推理历史 (List[str])
        FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )
    ''')
    
    # === [新增] 深度写作项目表 ===
    c.execute('''
    CREATE TABLE IF NOT EXISTS writing_projects (
        id TEXT PRIMARY KEY,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- 配置信息
        requirements TEXT,     -- 用户输入的需求/Prompt
        source_type TEXT,      -- "kb", "file", "text"
        source_data TEXT,      -- 知识库名 或 文件内容
        
        -- 生成内容
        research_report TEXT,  -- 调研报告 (Markdown)
        outline_data TEXT,     -- 大纲结构 (JSON)
        full_draft TEXT        -- 最终生成的正文 (Markdown)
    )
    ''')

    conn.commit()
    conn.close()

def create_session(title: str = "新对话") -> str:
    """创建新会话并返回 session_id"""
    session_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT INTO sessions (id, title) VALUES (?, ?)", (session_id, title))
    conn.commit()
    conn.close()
    return session_id

def update_session_title(session_id: str, title: str):
    """更新会话标题"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
    conn.commit()
    conn.close()

def get_all_sessions() -> List[Dict]:
    """获取所有会话，按时间倒序排列"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_session(session_id: str):
    """删除会话及其消息"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    # 由于设置了 ON DELETE CASCADE (如果 SQLite 支持并开启)，消息会自动删除
    # 为保险起见手动删除
    c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

def add_message(session_id: str, role: str, content: str):
    """添加一条消息"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
              (session_id, role, content))
    conn.commit()
    conn.close()

def get_messages(session_id: str) -> List[Dict]:
    """获取指定会话的所有消息"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# === 新增：报告管理函数 ===

def save_report(title: str, source_name: str, content: str) -> str:
    """保存一份新的深度解读报告"""
    report_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    # 如果标题太长，截断一下
    if len(title) > 50: title = title[:50] + "..."
        
    c.execute(
        "INSERT INTO research_reports (id, title, source_name, content) VALUES (?, ?, ?, ?)",
        (report_id, title, source_name, content)
    )
    conn.commit()
    conn.close()
    return report_id

def get_all_reports() -> List[Dict]:
    """获取所有报告列表（按时间倒序）"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, title, source_name, created_at FROM research_reports ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_report_content(report_id: str) -> Optional[Dict]:
    """获取特定报告的详细内容"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM research_reports WHERE id = ?", (report_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_report(report_id: str):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM research_reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()

# === [新增] 上下文管理函数 ===

def save_session_artifact(session_id: str, doc_title: str, doc_content: str, qa_pairs: List[str]):
    """保存或更新会话的文档和推理历史"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    qa_pairs_json = json.dumps(qa_pairs, ensure_ascii=False)
    
    c.execute('''
    INSERT OR REPLACE INTO session_artifacts (session_id, doc_title, doc_content, qa_pairs)
    VALUES (?, ?, ?, ?)
    ''', (session_id, doc_title, doc_content, qa_pairs_json))
    
    conn.commit()
    conn.close()

def get_session_artifact(session_id: str) -> Optional[Dict]:
    """获取会话的文档和推理历史"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM session_artifacts WHERE session_id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        data = dict(row)
        # 反序列化 qa_pairs
        try:
            data['qa_pairs'] = json.loads(data['qa_pairs'])
        except:
            data['qa_pairs'] = []
        return data
    return None

def update_session_qa_pairs(session_id: str, qa_pairs: List[str]):
    """仅更新推理历史"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    qa_pairs_json = json.dumps(qa_pairs, ensure_ascii=False)
    c.execute("UPDATE session_artifacts SET qa_pairs = ? WHERE session_id = ?", (qa_pairs_json, session_id))
    conn.commit()
    conn.close()

# === [新增] 写作项目 CRUD 函数 ===

def create_writing_project(title: str, requirements: str, source_type: str, source_data: str) -> str:
    project_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        INSERT INTO writing_projects (id, title, requirements, source_type, source_data, outline_data, full_draft)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (project_id, title, requirements, source_type, source_data, "[]", ""))
    conn.commit()
    conn.close()
    return project_id

def get_writing_project(project_id: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM writing_projects WHERE id = ?", (project_id,))
    row = c.fetchone()
    conn.close()
    if row:
        data = dict(row)
        # 尝试解析 outline_data
        try:
            data['outline_data'] = json.loads(data['outline_data'])
        except:
            data['outline_data'] = []
        return data
    return None

def update_project_outline(project_id: str, outline_data: List[Dict], research_report: str = None):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    outline_json = json.dumps(outline_data, ensure_ascii=False)
    
    if research_report:
        c.execute("UPDATE writing_projects SET outline_data = ?, research_report = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                  (outline_json, research_report, project_id))
    else:
        c.execute("UPDATE writing_projects SET outline_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                  (outline_json, project_id))
    conn.commit()
    conn.close()

def update_project_draft(project_id: str, full_draft: str):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE writing_projects SET full_draft = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
              (full_draft, project_id))
    conn.commit()
    conn.close()

def get_all_projects() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, title, created_at FROM writing_projects ORDER BY updated_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_project(project_id: str):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM writing_projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()