import os

def save_python_files(base_dir):
    output_path = os.path.join(base_dir, "all_python_files.txt")

    with open(output_path, "w", encoding="utf-8") as out:
        for root, dirs, files in os.walk(base_dir):
            # 去掉 venv
            if "venv" in dirs:
                dirs.remove("venv")

            for fname in files:
                if fname.endswith(".py"):
                    full_path = os.path.join(root, fname)

                    out.write(full_path + "\n")
                    out.write("-" * 80 + "\n")

                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            out.write(f.read())
                    except UnicodeDecodeError:
                        with open(full_path, "r", encoding="latin-1") as f:
                            out.write(f.read())

                    out.write("\n\n")

    print(f"Very good, sir. 已生成：{output_path}")

if __name__ == "__main__":
    base_directory = "."
    save_python_files(base_directory)
