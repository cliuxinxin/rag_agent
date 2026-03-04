import os
import subprocess
import sys

def save_all_code(base_dir, include_deploy=True):
    """
    保存所有代码和部署配置到 txt 文件
    
    Args:
        base_dir: 基础目录
        include_deploy: 是否包含部署相关文件 (Dockerfile, docker-compose.yml, deploy.yml 等)
    """
    output_path = os.path.join(base_dir, "all_python_files.txt")
    
    # 定义部署相关的文件扩展名和文件名
    deploy_files = {"Dockerfile", "docker-compose.yml", "deploy.yml"}
    config_extensions = {".yaml", ".yml", ".json", ".toml"}
    md_files = {"README.md", "MIGRATION_PLAN.md", "QUICK_START.md", "MIGRATION_PROGRESS.md"}
    
    with open(output_path, "w", encoding="utf-8") as out:
        for root, dirs, files in os.walk(base_dir):
            # 去掉 venv
            if "venv" in dirs:
                dirs.remove("venv")
            
            # 跳过一些不需要的目录
            skip_dirs = {"__pycache__", ".git", ".langgraph_api", "logs", "storage", ".qoder"}
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for fname in files:
                full_path = os.path.join(root, fname)
                should_include = False
                
                # Python 文件
                if fname.endswith(".py"):
                    should_include = True
                
                # 部署相关文件
                elif include_deploy and fname in deploy_files:
                    should_include = True
                
                # GitHub Actions 部署文件
                elif include_deploy and "deploy.yml" in fname and ".github/workflows" in root:
                    should_include = True
                
                # Markdown 文档（新增）
                elif fname in md_files:
                    should_include = True
                
                # 其他配置文件（可选）
                elif include_deploy and any(fname.endswith(ext) for ext in config_extensions):
                    # 只收集重要的配置文件
                    important_configs = {"config.yaml", "requirements.txt", ".env.example"}
                    if fname in important_configs:
                        should_include = True
                
                if should_include:
                    rel_path = os.path.relpath(full_path, base_dir)
                    out.write(f"📁 {rel_path}\n")
                    out.write("=" * 80 + "\n")

                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            out.write(content)
                    except UnicodeDecodeError:
                        try:
                            with open(full_path, "r", encoding="latin-1") as f:
                                content = f.read()
                                out.write(content)
                        except Exception as e:
                            out.write(f"无法读取文件：{e}\n")
                    except Exception as e:
                        out.write(f"读取错误：{e}\n")

                    out.write("\n\n" + "=" * 80 + "\n\n")

    print(f"✅ Very good, sir. 已生成：{output_path}")
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
