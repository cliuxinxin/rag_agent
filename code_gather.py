import os
import subprocess
import sys

def save_all_code(base_dir, include_deploy=True):
    """
    保存所有代码和部署配置到 txt 文件
    """
    output_path = os.path.join(base_dir, "project_source_code.txt")
    
    deploy_files = {"Dockerfile", "docker-compose.yml", "deploy.yml"}
    config_extensions = {".yaml", ".yml", ".json", ".toml", ".ini"}
    frontend_extensions = {".vue", ".ts", ".tsx", ".js", ".jsx"}
    
    # ❌ 扩充黑名单目录：包含所有常见的编译产物、缓存、依赖包
    skip_dirs = {
        # Python 相关
        "__pycache__", "venv", "env", ".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov",
        # 前端相关
        "node_modules", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", "coverage", ".output",
        # 工具和系统相关
        ".git", ".vscode", ".idea", ".husky", "logs", "storage", ".qoder", ".langgraph_api", "tmp", "temp"
    }
    
    # ❌ 扩充黑名单文件：排除 Lock 文件和系统隐藏文件
    exclude_files = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
        "project_source_code.txt", "all_python_files.txt", 
        ".DS_Store", "Thumbs.db"
    }
    
    # ❌ 黑名单后缀名：排除编译后的产物和类型文件
    exclude_extensions = {
        ".map", ".pyc", ".pyo", ".pyd", ".so", ".dll", ".class", ".exe"
    }
    
    with open(output_path, "w", encoding="utf-8") as out:
        for root, dirs, files in os.walk(base_dir):
            # 1. 第一道防线：告诉 os.walk 不要进入黑名单目录
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for fname in files:
                # 2. 第二道防线：过滤黑名单文件和黑名单后缀
                if fname in exclude_files or any(fname.endswith(ext) for ext in exclude_extensions):
                    continue
                    
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, base_dir)
                rel_path_unix = rel_path.replace("\\", "/") # 统一转为 Unix 风格路径，方便判断
                
                # 3. 第三道防线（双重保险）：强制检查路径的所有级目录
                # 防止由于某些奇葩嵌套（如 a/b/dist/src/x.js）导致前面漏判
                path_parts = set(rel_path_unix.split("/"))
                if path_parts.intersection(skip_dirs):
                    continue
                
                should_include = False
                
                # 规则 1. Python 文件
                if fname.endswith(".py"):
                    should_include = True
                
                # 规则 2. 前端源文件
                elif any(fname.endswith(ext) for ext in frontend_extensions):
                    # 必须在 src 目录下，且排除 .min.js 压缩文件和 .d.ts 自动生成的类型文件
                    if ("frontend/src" in rel_path_unix or "src/" in rel_path_unix):
                        if not (fname.endswith(".min.js") or fname.endswith(".d.ts")):
                            should_include = True
                
                # 规则 3. 部署相关文件
                elif include_deploy and fname in deploy_files:
                    should_include = True
                elif include_deploy and "deploy.yml" in fname and ".github/workflows" in rel_path_unix:
                    should_include = True
                
                # 规则 4. 其他核心配置文件 (添加了前端常见配置)
                elif include_deploy and any(fname.endswith(ext) for ext in config_extensions):
                    important_configs = {
                        "config.yaml", "requirements.txt", ".env.example", 
                        "package.json", "vite.config.ts", "tsconfig.json", 
                        "tailwind.config.js", "tailwind.config.ts", "postcss.config.js"
                    }
                    if fname in important_configs:
                        should_include = True
                
                if should_include:
                    # 保护机制：如果文件大于 500KB，大概率是数据文件、图片或混淆后的 JS，跳过
                    if os.path.getsize(full_path) > 500 * 1024:
                        print(f"⚠️ 跳过超大文件: {rel_path_unix}")
                        continue
                        
                    out.write(f"📁 {rel_path_unix}\n")
                    out.write("=" * 80 + "\n")

                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            out.write(f.read())
                    except UnicodeDecodeError:
                        out.write("【此文件包含无法解析的非文本内容，已跳过】\n")
                    except Exception as e:
                        out.write(f"【读取错误：{e}】\n")

                    out.write("\n\n" + "=" * 80 + "\n\n")

    print(f"✅ 代码收集完成，已生成：{output_path}")
    return output_path


def check_env_file():
    """检查 .env 文件是否存在"""
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        print("⚠️  警告：.env 文件不存在，请确保已配置环境变量")
        return False
    print("✅ .env 文件检查通过")
    return True


def check_requirements():
    """检查 requirements.txt 是否存在"""
    req_path = os.path.join(os.getcwd(), "requirements.txt")
    if not os.path.exists(req_path):
        print("❌ 错误：requirements.txt 文件不存在")
        return False
    print("✅ requirements.txt 检查通过")
    return True


def build_docker_image(image_name="deepseek_rag_pro"):
    """构建 Docker 镜像"""
    print("🔨 开始构建 Docker 镜像...")
    try:
        result = subprocess.run(
            ["docker", "build", "-t", image_name, "."],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ Docker 镜像构建成功：{image_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker 镜像构建失败：{e}")
        print(e.stderr)
        return False
    except FileNotFoundError:
        print("❌ 错误：未找到 docker 命令，请确保已安装 Docker")
        return False


def start_container(detach=True):
    """启动 Docker 容器"""
    print("🚀 开始启动 Docker 容器...")
    try:
        cmd = ["docker-compose", "up"]
        if detach:
            cmd.append("-d")
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Docker 容器启动成功")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker 容器启动失败：{e}")
        print(e.stderr)
        return False
    except FileNotFoundError:
        print("❌ 错误：未找到 docker-compose 命令，请确保已安装 Docker Compose")
        return False


def stop_container():
    """停止 Docker 容器"""
    print("🛑 停止 Docker 容器...")
    try:
        result = subprocess.run(
            ["docker-compose", "down"],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ Docker 容器已停止")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 停止容器失败：{e}")
        print(e.stderr)
        return False


def check_container_status():
    """检查容器运行状态"""
    print("📊 检查容器运行状态...")
    try:
        result = subprocess.run(
            ["docker-compose", "ps"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.returncode == 0:
            print("✅ 容器状态检查完成")
            return True
        else:
            print("⚠️  容器未运行或出现错误")
            return False
    except FileNotFoundError:
        print("❌ 错误：未找到 docker-compose 命令")
        return False


def view_logs(follow=False, tail=100):
    """查看容器日志"""
    print(f"📋 查看容器日志 (最近 {tail} 行)...")
    try:
        cmd = ["docker-compose", "logs", f"--tail={tail}"]
        if follow:
            cmd.append("-f")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        return True
    except Exception as e:
        print(f"❌ 查看日志失败：{e}")
        return False


def deploy_production(host=None, username=None):
    """生产环境部署（模拟 GitHub Actions 流程）"""
    print("🌐 开始生产环境部署...")
    
    if host and username:
        print(f"📡 准备部署到远程服务器：{username}@{host}")
        # 这里可以添加 SSH 远程部署逻辑
        print("ℹ️  提示：生产环境部署通常通过 GitHub Actions 自动完成")
        print("   配置文件：.github/workflows/deploy.yml")
    else:
        print("📦 执行本地部署...")
        
        # 1. 检查环境
        if not check_env_file() or not check_requirements():
            print("❌ 环境检查失败，无法继续部署")
            return False
        
        # 2. 构建镜像
        if not build_docker_image():
            print("❌ 镜像构建失败")
            return False
        
        # 3. 停止旧容器
        stop_container()
        
        # 4. 启动新容器
        if not start_container(detach=True):
            print("❌ 容器启动失败")
            return False
        
        # 5. 验证部署
        import time
        time.sleep(3)  # 等待容器启动
        check_container_status()
        
        print("\n✅ 部署完成！")
        print("📌 访问地址：http://localhost:8000")
        print("📌 查看日志：docker-compose logs -f")
        print("📌 停止服务：docker-compose down")
        return True


if __name__ == "__main__":
    base_directory = "."
    
    # 默认执行完整的代码收集（包含部署文件）
    save_all_code(base_directory, include_deploy=True)
    
    # 如果传入部署参数，则执行部署流程
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "deploy":
            deploy_production()
        elif command == "build":
            build_docker_image()
        elif command == "start":
            start_container()
        elif command == "stop":
            stop_container()
        elif command == "status":
            check_container_status()
        elif command == "logs":
            follow = "-f" in sys.argv
            view_logs(follow=follow)
        elif command == "collect":
            # 仅收集代码，不包含部署文件
            save_all_code(base_directory, include_deploy=False)
        else:
            print(f"未知命令：{command}")
            print("可用命令：deploy, build, start, stop, status, logs, collect")
