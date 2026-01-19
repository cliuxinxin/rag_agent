import sys
import json
import os
import shutil
import ast
from pathlib import Path

def validate_code(code: str) -> str:
    """静态代码分析，防止生成无法运行的垃圾代码"""
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return str(e)

def create_skill(json_str):
    try:
        # 1. 解析 JSON
        data = json.loads(json_str)
        folder_name = data.get("folder_name")
        files = data.get("files", [])

        if not folder_name:
            print("Error: 'folder_name' is missing.")
            return

        # 2. 路径定位
        current_dir = Path(__file__).parent
        skills_root = current_dir.parent.parent # 回退到 skills/ 根目录
        target_dir = skills_root / folder_name

        # 3. 【关键修复】处理文件夹冲突
        # 如果文件夹已存在，不要报错退出，而是视为“更新模式”
        if not target_dir.exists():
            target_dir.mkdir(parents=True)
            print(f"Created directory: {target_dir}")
        else:
            print(f"Directory exists. Updating skill: {folder_name}...")

        # 4. 预检查：所有 Python 代码必须通过语法验证
        for f in files:
            if f['path'].endswith('.py'):
                err = validate_code(f['content'])
                if err:
                    print(f"❌ Syntax Error in {f['path']}: {err}")
                    print("Action: Please FIX the code syntax and try again.")
                    return

        # 5. 写入文件
        written_files = []
        for f in files:
            # 相对路径转绝对路径
            file_path = target_dir / f['path']
            
            # 确保子文件夹存在 (如 scripts/)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as file_out:
                file_out.write(f['content'])
            
            written_files.append(f['path'])

        print(f"✅ Skill '{folder_name}' created successfully!")
        print("Manifest:")
        for name in written_files:
            print(f" - {name}")
        print("\nIMPORTANT: Tell the user to refresh the app to load the new skill.")

    except json.JSONDecodeError:
        print("Error: Invalid JSON string. Please check quotes escaping.")
    except Exception as e:
        print(f"System Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 拼接参数，防止 Agent 传参时被空格截断
        full_json = " ".join(sys.argv[1:])
        create_skill(full_json)
    else:
        print("Error: No JSON input provided.")