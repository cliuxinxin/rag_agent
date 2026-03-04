"""
Backend Package
"""
import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.join(os.path.dirname(__file__), '..')
if project_root not in sys.path:
    sys.path.insert(0, project_root)
