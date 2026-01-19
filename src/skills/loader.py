# src/skills/loader.py
import os
import frontmatter as fm
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

# 指向根目录下的 skills 文件夹
# 获取当前文件 (loader.py) 所在的目录: /app/src/skills
CURRENT_DIR = Path(__file__).parent.resolve()
# 回退两级到 /app，然后指向 skills
# 假设结构是 /app/src/skills/loader.py -> /app/skills
SKILLS_ROOT = CURRENT_DIR.parent.parent / "skills"

# 打印一下路径方便调试 (在 docker logs 中能看到)
print(f"DEBUG: Loading skills from: {SKILLS_ROOT}")

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