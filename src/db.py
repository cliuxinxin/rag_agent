import sqlite3
import os
import uuid
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from contextlib import contextmanager
from src.logger import get_logger

logger = get_logger("Database")

# === 路径配置 ===
SRC_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = SRC_DIR.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = STORAGE_DIR / "chat_history.db"

class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_optimization()

    def _init_optimization(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception as e:
            logger.error(f"DB 优化失败: {e}")

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=60.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ 数据库事务回滚: {e}", exc_info=True)
            raise e
        finally:
            conn.close()

db_manager = DatabaseManager(DB_PATH)

_DB_INITIALIZED = False

def init_db():
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    
    logger.info(f"初始化数据库: {DB_PATH}")
    try:
        with db_manager.get_connection() as conn:
            c = conn.cursor()
            
            c.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

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

            c.execute('''
            CREATE TABLE IF NOT EXISTS research_reports (
                id TEXT PRIMARY KEY,
                title TEXT,
                source_name TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            c.execute('''
            CREATE TABLE IF NOT EXISTS session_artifacts (
                session_id TEXT PRIMARY KEY,
                doc_title TEXT,
                doc_content TEXT,
                qa_pairs TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            ''')
            
            c.execute('''
            CREATE TABLE IF NOT EXISTS writing_projects (
                id TEXT PRIMARY KEY,
                title TEXT,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                requirements TEXT,
                source_type TEXT,
                source_data TEXT,
                outline_data TEXT,
                full_draft TEXT,
                assets_data TEXT,
                logs TEXT,
                process_data TEXT
            )
            ''')
            
            # 自动迁移：检查并添加缺失的列
            columns_to_ensure = [
                ("logs", "TEXT"),
                ("status", "TEXT DEFAULT 'draft'"),
                ("assets_data", "TEXT"),
                ("process_data", "TEXT")
            ]
            
            for col_name, col_type in columns_to_ensure:
                try:
                    c.execute(f"ALTER TABLE writing_projects ADD COLUMN {col_name} {col_type}")
                    logger.info(f"🔄 [DB迁移] 成功添加新列: {col_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e):
                        pass  # 列已存在，正常跳过
                    else:
                        logger.warning(f"⚠️ [DB迁移] 列 {col_name} 检查警告: {e}")
            
            c.execute('''
            CREATE TABLE IF NOT EXISTS mastery_sessions (
                id TEXT PRIMARY KEY,
                topic TEXT,
                concepts_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

        logger.info("✅ 数据库结构检查/修复完成")
        _DB_INITIALIZED = True
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        raise e

def create_session(title: str = "新对话") -> str:
    session_id = str(uuid.uuid4())
    try:
        with db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO sessions (id, title) VALUES (?, ?)", (session_id, title))
        logger.info(f"创建新会话: {session_id} - {title}")
        return session_id
    except Exception as e:
        logger.error(f"创建会话失败: {e}", exc_info=True)
        return session_id

def update_session_title(session_id: str, title: str):
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))

def get_all_sessions() -> List[Dict]:
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        rows = c.fetchall()
        return [dict(row) for row in rows]

def delete_session(session_id: str):
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

def add_message(session_id: str, role: str, content: str):
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                  (session_id, role, content))

def get_messages(session_id: str) -> List[Dict]:
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
        rows = c.fetchall()
        return [dict(row) for row in rows]

def save_report(title: str, source_name: str, content: str) -> str:
    report_id = str(uuid.uuid4())
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        if len(title) > 50: title = title[:50] + "..."
        c.execute(
            "INSERT INTO research_reports (id, title, source_name, content) VALUES (?, ?, ?, ?)",
            (report_id, title, source_name, content)
        )
    return report_id

def get_all_reports() -> List[Dict]:
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, title, source_name, created_at FROM research_reports ORDER BY created_at DESC")
        rows = c.fetchall()
        return [dict(row) for row in rows]

def get_report_content(report_id: str) -> Optional[Dict]:
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM research_reports WHERE id = ?", (report_id,))
        row = c.fetchone()
        return dict(row) if row else None

def delete_report(report_id: str):
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM research_reports WHERE id = ?", (report_id,))

def save_session_artifact(session_id: str, doc_title: str, doc_content: str, qa_pairs: List[str]):
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        qa_pairs_json = json.dumps(qa_pairs, ensure_ascii=False)
        c.execute('''
        INSERT OR REPLACE INTO session_artifacts (session_id, doc_title, doc_content, qa_pairs)
        VALUES (?, ?, ?, ?)
        ''', (session_id, doc_title, doc_content, qa_pairs_json))

def get_session_artifact(session_id: str) -> Optional[Dict]:
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM session_artifacts WHERE session_id = ?", (session_id,))
        row = c.fetchone()
        if row:
            data = dict(row)
            try:
                data['qa_pairs'] = json.loads(data['qa_pairs'])
            except:
                data['qa_pairs'] = []
            return data
    return None

def update_session_qa_pairs(session_id: str, qa_pairs: List[str]):
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        qa_pairs_json = json.dumps(qa_pairs, ensure_ascii=False)
        c.execute("UPDATE session_artifacts SET qa_pairs = ? WHERE session_id = ?", (qa_pairs_json, session_id))

# === 核心 CRUD 修复 ===

def create_writing_project(title: str, requirements: str, source_type: str, source_data: str, project_id: Optional[str] = None) -> str:
    if project_id is None:
        project_id = str(uuid.uuid4())
    logger.info(f"正在创建项目 ID: {project_id} | Title: {title}")
    
    with db_manager.get_connection() as conn:
        cursor = conn.execute('''
            INSERT INTO writing_projects (id, title, requirements, source_type, source_data, outline_data, full_draft, logs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, title, requirements, source_type, source_data, "[]", "", "[]"))
        logger.info(f"✅ 项目创建成功，影响行数: {cursor.rowcount}")
        
    return project_id

def update_project_title(project_id: str, title: str):
    with db_manager.get_connection() as conn:
        cursor = conn.execute("UPDATE writing_projects SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                  (title, project_id))
        if cursor.rowcount == 0:
            logger.error(f"❌ 标题更新失败：找不到 ID {project_id}")
        else:
            logger.info(f"✅ 标题更新成功: {title}")

def update_project_draft(project_id: str, full_draft: str):
    logger.info(f"正在保存草稿 ID: {project_id} | 长度: {len(full_draft)} chars")
    
    with db_manager.get_connection() as conn:
        cursor = conn.execute("UPDATE writing_projects SET full_draft = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                  (full_draft, project_id))
        
        if cursor.rowcount == 0:
            logger.error(f"❌ 草稿保存失败：数据库中找不到 ID {project_id}")
        else:
            logger.info(f"✅ 草稿保存成功 (Rows: {cursor.rowcount})")

def update_project_outline(project_id: str, outline_data: list):
    with db_manager.get_connection() as conn:
        conn.execute("UPDATE writing_projects SET outline_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                  (json.dumps(outline_data, ensure_ascii=False), project_id))

def get_writing_project(project_id: str) -> dict:
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT * FROM writing_projects WHERE id = ?", (project_id,)).fetchone()
        if row:
            res = dict(row)
            for field in ['requirements', 'outline_data', 'assets_data', 'logs', 'process_data']:
                if res.get(field):
                    try:
                        res[field] = json.loads(res[field])
                    except: res[field] = [] if field == 'logs' else {}
            return res
    return None

def get_all_projects():
    with db_manager.get_connection() as conn:
        cursor = conn.execute("SELECT id, title, source_type, created_at, updated_at FROM writing_projects ORDER BY updated_at DESC")
        return [dict(row) for row in cursor.fetchall()]
        
def delete_project(project_id: str):
    with db_manager.get_connection() as conn:
        conn.execute("DELETE FROM writing_projects WHERE id = ?", (project_id,))

def get_projects_by_source(source_type: str) -> List[Dict]:
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, title, source_type, created_at, updated_at FROM writing_projects WHERE source_type = ? ORDER BY updated_at DESC",
            (source_type,),
        )
        rows = c.fetchall()
        return [dict(row) for row in rows]

def create_mastery_session(topic: str) -> str:
    session_id = str(uuid.uuid4())
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute('''
        CREATE TABLE IF NOT EXISTS mastery_sessions (
            id TEXT PRIMARY KEY,
            topic TEXT,
            concepts_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        c.execute("INSERT INTO mastery_sessions (id, topic, concepts_data) VALUES (?, ?, ?)", 
                  (session_id, topic, "[]"))
    return session_id

def update_mastery_concepts(session_id: str, concepts: List[dict]):
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE mastery_sessions SET concepts_data = ? WHERE id = ?", 
                  (json.dumps(concepts, ensure_ascii=False), session_id))

def get_mastery_session(session_id: str) -> Optional[Dict]:
    try:
        with db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM mastery_sessions WHERE id = ?", (session_id,))
            row = c.fetchone()
            if row:
                data = dict(row)
                data['concepts_data'] = json.loads(data['concepts_data'])
                return data
    except Exception as e:
        logger.error(f"获取 master session 失败: {e}")
        return None
    return None

def get_all_mastery_sessions() -> List[Dict]:
    try:
        with db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM mastery_sessions ORDER BY created_at DESC")
            rows = c.fetchall()
            results = []
            for row in rows:
                d = dict(row)
                try:
                    d['concepts_data'] = json.loads(d['concepts_data'])
                except:
                    d['concepts_data'] = []
                results.append(d)
            return results
    except Exception as e:
        logger.error(f"获取列表失败: {e}")
        return []

def update_mastery_session_data(session_id: str, concepts_data: List[dict]):
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        json_str = json.dumps(concepts_data, ensure_ascii=False)
        c.execute("UPDATE mastery_sessions SET concepts_data = ? WHERE id = ?", 
                  (json_str, session_id))

def update_project_assets(project_id: str, assets: List[Dict]):
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE writing_projects SET assets_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                  (json.dumps(assets, ensure_ascii=False), project_id))

def update_project_section_content(project_id: str, outline_data: List[Dict]):
    with db_manager.get_connection() as conn:
        c = conn.cursor()
        full_text = "\n\n".join([f"## {sec['title']}\n\n{sec.get('content','')}" for sec in outline_data])
        c.execute("UPDATE writing_projects SET outline_data = ?, full_draft = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                  (json.dumps(outline_data, ensure_ascii=False), full_text, project_id))

# [新增] 更新过程数据
def update_project_process_data(project_id: str, data: dict):
    with db_manager.get_connection() as conn:
        # 先读取旧数据合并（简单的 JSON Merge）
        row = conn.execute("SELECT process_data FROM writing_projects WHERE id = ?", (project_id,)).fetchone()
        old_data = {}
        if row and row[0]:
            try:
                old_data = json.loads(row[0])
            except: pass
        
        # 合并
        new_data = {**old_data, **data}
        
        conn.execute("UPDATE writing_projects SET process_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                  (json.dumps(new_data, ensure_ascii=False), project_id))
        logger.info(f"✅ 过程数据已更新: {project_id}")

# [新增] 追加日志到数据库
def append_project_log(project_id: str, log_entry: dict):
    """
    log_entry 结构: {"step": "Writer", "input": "...", "output": "...", "timestamp": "..."}
    """
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT logs FROM writing_projects WHERE id = ?", (project_id,)).fetchone()
        logs = []
        if row and row[0]:
            try:
                logs = json.loads(row[0])
            except: pass
        
        logs.append(log_entry)
        conn.execute("UPDATE writing_projects SET logs = ? WHERE id = ?", 
                  (json.dumps(logs, ensure_ascii=False), project_id))
        logger.info(f"📝 日志已记录: {project_id} - {log_entry.get('stage', 'unknown')}")

def delete_mastery_session(session_id: str):
    """删除学习记录"""
    with db_manager.get_connection() as conn:
        conn.execute("DELETE FROM mastery_sessions WHERE id = ?", (session_id,))
