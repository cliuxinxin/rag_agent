# src/skills/loader.py
import os
import frontmatter as fm
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

# === 🚀 终极稳健写法 ===
# 不管是本地还是 Docker，我们都基于"当前工作目录"来找
# 在 Docker 里，CWD 是 /app -> 路径就是 /app/skills
# 在 本地启动，CWD 是项目根目录 -> 路径就是 ./skills
CWD = Path(os.getcwd())
SKILLS_ROOT = CWD / "skills"

print(f"DEBUG: Current Working Directory: {CWD}")
print(f"DEBUG: Target SKILLS_ROOT: {SKILLS_ROOT}")

class SkillMetadata(TypedDict):
    name: str
    description: str
    version: Optional[str]
    author: Optional[str]

class AgentSkill:
    def __init__(self, path: Path):
        self.root_path = path
        self.skill_file = path / "SKILL.md"
        self._load()

    def _load(self):
        if not self.skill_file.exists():
            raise FileNotFoundError(f"Missing SKILL.md in {self.root_path}")
        
        # Use the correct API for python-frontmatter package
        post = fm.load(str(self.skill_file))
        
        self.metadata = SkillMetadata(
            name=post.metadata.get("name", self.root_path.name),
            description=post.metadata.get("description", "No description provided."),
            version=str(post.metadata.get("version", "1.0")),
            author=post.metadata.get("author", "Unknown")
        )
        self.instructions = post.content

    @property
    def name(self):
        return self.metadata["name"]

class SkillRegistry:
    def __init__(self):
        # 强制建立目录（防止报错）
        if not SKILLS_ROOT.exists():
            print(f"❌ 警告: 目录 {SKILLS_ROOT} 不存在，尝试创建...")
            try:
                SKILLS_ROOT.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"❌ 创建失败: {e}")

        self.skills: Dict[str, AgentSkill] = {}
        self.refresh()

    def refresh(self):
        self.skills = {}
        
        # 🔍 打印详细遍历日志
        if SKILLS_ROOT.exists():
            print(f"📂 开始遍历: {SKILLS_ROOT}")
            for item in SKILLS_ROOT.iterdir():
                if item.is_dir():
                    # 关键检查点：文件名必须是大写的 SKILL.md
                    skill_file = item / "SKILL.md"
                    
                    if skill_file.exists():
                        try:
                            skill = AgentSkill(item)
                            self.skills[skill.name] = skill
                            print(f"   ✅ 加载成功: {skill.name}")
                        except Exception as e:
                            print(f"   ❌ 加载出错 {item.name}: {e}")
                    else:
                        # 检查是不是大小写搞错了
                        files = [f.name for f in item.glob("*")]
                        print(f"   ⚠️ 忽略文件夹 {item.name}: 没找到 SKILL.md. 现有文件: {files}")
        else:
            print("❌ SKILLS_ROOT 目录根本不存在！")

    def get_skill(self, name: str) -> Optional[AgentSkill]:
        return self.skills.get(name)

    def list_skills(self) -> List[Dict]:
        return [s.metadata for s in self.skills.values()]