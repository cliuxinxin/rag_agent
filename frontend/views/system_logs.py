# frontend/views/system_logs.py
import streamlit as st
import os
from collections import deque
from pathlib import Path

# 定义日志路径
LOG_DIR = Path("logs")
APP_LOG_PATH = LOG_DIR / "app.log"
ERROR_LOG_PATH = LOG_DIR / "error.log"

def read_last_lines(file_path: Path, num_lines: int = 100) -> str:
    """
    高效读取文件最后 N 行，防止内存溢出
    """
    if not file_path.exists():
        return f"⚠️ 日志文件不存在: {file_path}"
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            # deque(f, maxlen=N) 是 Python 中实现 tail 最快的方法
            lines = deque(f, maxlen=num_lines)
            return "".join(lines)
    except Exception as e:
        return f"❌ 读取日志出错: {e}"

def get_file_size(file_path: Path) -> str:
    """获取文件大小的可读格式"""
    if not file_path.exists():
        return "0 KB"
    size_bytes = file_path.stat().st_size
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def render():
    st.header("🛠️ 系统运行日志")
    st.caption("实时监控后台运行状态、错误信息及调试记录。")

    # === 工具栏 ===
    col1, col2, col3 = st.columns([2, 2, 6])
    with col1:
        # 选择查看行数
        lines_to_show = st.selectbox("查看行数 (Tail)", [50, 100, 500, 1000], index=1)
    with col2:
        # 刷新按钮
        if st.button("🔄 刷新日志", use_container_width=True):
            st.rerun()
    
    st.divider()

    # === 日志显示区域 ===
    tab1, tab2 = st.tabs(["📝 运行日志 (App Log)", "🚨 错误日志 (Error Log)"])

    # --- 运行日志 ---
    with tab1:
        size = get_file_size(APP_LOG_PATH)
        st.markdown(f"**文件状态**: `{APP_LOG_PATH}` | 大小: **{size}**")
        
        log_content = read_last_lines(APP_LOG_PATH, lines_to_show)
        
        # 使用 code 块显示，支持滚动和复制，设置 language='log' (虽然 Streamlit 不一定支持 log 高亮，但格式更好)
        st.code(log_content, language="accesslog", line_numbers=True)
        
        # 下载按钮
        if APP_LOG_PATH.exists():
            with open(APP_LOG_PATH, "rb") as f:
                st.download_button(
                    label="📥 下载完整运行日志",
                    data=f,
                    file_name="app_full.log",
                    mime="text/plain"
                )

    # --- 错误日志 ---
    with tab2:
        size = get_file_size(ERROR_LOG_PATH)
        st.markdown(f"**文件状态**: `{ERROR_LOG_PATH}` | 大小: **{size}**")
        
        if ERROR_LOG_PATH.exists():
            error_content = read_last_lines(ERROR_LOG_PATH, lines_to_show)
            if not error_content.strip():
                st.success("✅ 暂无严重错误记录。")
            else:
                # 错误日志用红色边框警告
                st.warning("⚠️ 检测到错误记录，请检查下方日志：")
                st.code(error_content, language="accesslog", line_numbers=True)
                
            with open(ERROR_LOG_PATH, "rb") as f:
                st.download_button(
                    label="📥 下载完整错误日志",
                    data=f,
                    file_name="error_full.log",
                    mime="text/plain"
                )
        else:
            st.info("暂无错误日志文件。")

