# src/skills/loader.py
import os
import frontmatter as fm
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

# 获取当前脚本绝对路径: /app/src/skills/loader.py
CURRENT_SCRIPT_PATH = Path(__file__).resolve()

# 回退到项目根目录 /app
# 逻辑：loader.py -> src/skills/ -> src/ -> app/
PROJECT_ROOT = CURRENT_SCRIPT_PATH.parent.parent.parent

# 指向 /app/skills
SKILLS_ROOT = PROJECT_ROOT / "skills"

# 添加调试打印 (在 docker logs 中能看到)
print(f"--- DEBUG ---")
print(f"Loader Path: {CURRENT_SCRIPT_PATH}")
print(f"Project Root: {PROJECT_ROOT}")
print(f"Skills Dir: {SKILLS_ROOT}")
print(f"Exists?: {SKILLS_ROOT.exists()}")
print(f"----------------")

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
        
        # Use the correct API for this version of frontmatter
        result = fm.Frontmatter.read_file(str(self.skill_file))
        post = type('Post', (), {})()  # Create a dummy object
        post.metadata = result['attributes']
        post.content = result['body']
        
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
        SKILLS_ROOT.mkdir(exist_ok=True)
        self.skills: Dict[str, AgentSkill] = {}
        self.refresh()

    def refresh(self):
        self.skills = {}
        for item in SKILLS_ROOT.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                try:
                    skill = AgentSkill(item)
                    self.skills[skill.name] = skill
                except Exception as e:
                    print(f"Error loading skill {item.name}: {e}")

    def get_skill(self, name: str) -> Optional[AgentSkill]:
        return self.skills.get(name)

    def list_skills(self) -> List[Dict]:
        return [s.metadata for s in self.skills.values()]