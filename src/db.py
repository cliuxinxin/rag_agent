import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Optional

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