import sqlite3
import uuid
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from src.logger import get_logger

# 初始化日志
logger = get_logger("Database")

# === 路径配置 ===
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)
DB_PATH = STORAGE_DIR / "chat_history.db"

# 简单的防止单次运行中重复刷日志
# 注意：Streamlit 重运行时会重置，但可以减少单次会话内的重复日志
_DB_INITIALIZED = False

def init_db():
    """初始化数据库表结构"""
    global _DB_INITIALIZED
    
    # 简单的防止单次运行中重复刷日志
    # 如果想彻底防止 Streamlit 刷新带来的日志，可以用 st.session_state 判断
    if _DB_INITIALIZED:
        return
    
    logger.info(f"正在初始化数据库: {DB_PATH}")
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # 1. 会话表
        c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # 2. 消息表
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

        # 3. 深度解读报告表
        c.execute('''
        CREATE TABLE IF NOT EXISTS research_reports (
            id TEXT PRIMARY KEY,
            title TEXT,
            source_name TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # 4. 会话 Artifact 表
        c.execute('''
        CREATE TABLE IF NOT EXISTS session_artifacts (
            session_id TEXT PRIMARY KEY,
            doc_title TEXT,
            doc_content TEXT,
            qa_pairs TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        ''')
        
        # 5. 深度写作项目表
        # 注意：这里我们不需要 full_content 列，因为可以通过 source_data 恢复
        c.execute('''
        CREATE TABLE IF NOT EXISTS writing_projects (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- 配置信息
            requirements TEXT,     -- 用户需求
            source_type TEXT,      -- "kb", "file", "text"
            source_data TEXT,      -- 核心数据：KB名称列表(json) 或 文本内容
            
            -- 生成内容
            research_report TEXT,  -- 调研报告
            outline_data TEXT,     -- 大纲结构 (JSON)
            full_draft TEXT        -- 最终草稿
        )
        ''')

        conn.commit()
        conn.close()
        logger.info("数据库初始化完成")
        _DB_INITIALIZED = True
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        raise e

# === 基础 Session 操作 ===

def create_session(title: str = "新对话") -> str:
    session_id = str(uuid.uuid4())
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO sessions (id, title) VALUES (?, ?)", (session_id, title))
        conn.commit()
        conn.close()
        logger.info(f"创建新会话: {session_id} - {title}")
        return session_id
    except Exception as e:
        logger.error(f"创建会话失败: {e}", exc_info=True)
        return session_id

def update_session_title(session_id: str, title: str):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
    conn.commit()
    conn.close()

def get_all_sessions() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_session(session_id: str):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

def add_message(session_id: str, role: str, content: str):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
              (session_id, role, content))
    conn.commit()
    conn.close()

def get_messages(session_id: str) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# === 报告管理 ===

def save_report(title: str, source_name: str, content: str) -> str:
    report_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    if len(title) > 50: title = title[:50] + "..."
    c.execute(
        "INSERT INTO research_reports (id, title, source_name, content) VALUES (?, ?, ?, ?)",
        (report_id, title, source_name, content)
    )
    conn.commit()
    conn.close()
    return report_id

def get_all_reports() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, title, source_name, created_at FROM research_reports ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_report_content(report_id: str) -> Optional[Dict]:
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

# === Artifact 管理 ===

def save_session_artifact(session_id: str, doc_title: str, doc_content: str, qa_pairs: List[str]):
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
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM session_artifacts WHERE session_id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    if row:
        data = dict(row)
        try:
            data['qa_pairs'] = json.loads(data['qa_pairs'])
        except:
            data['qa_pairs'] = []
        return data
    return None

def update_session_qa_pairs(session_id: str, qa_pairs: List[str]):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    qa_pairs_json = json.dumps(qa_pairs, ensure_ascii=False)
    c.execute("UPDATE session_artifacts SET qa_pairs = ? WHERE session_id = ?", (qa_pairs_json, session_id))
    conn.commit()
    conn.close()

# === 写作项目 CRUD (核心修复区域) ===

def create_writing_project(title: str, requirements: str, source_type: str, source_data: str) -> str:
    """
    创建一个新的写作项目。
    注意：source_data 存储的是原数据（KB名字列表 或 文本），而不是 full_content。
    full_content 在运行时动态计算，不存数据库。
    """
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


def get_projects_by_source(source_type: str) -> List[Dict]:
    """按 source_type 查询项目列表（含更新时间）"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT id, title, source_type, created_at, updated_at FROM writing_projects WHERE source_type = ? ORDER BY updated_at DESC",
        (source_type,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_project(project_id: str):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM writing_projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()