def get_v3_system_prompt(assets_text: str, tone: str, length: str) -> str:
    return f"""你是由 DeepSeek 驱动的专业非虚构写作助手。
    
【核心素材库 (Context Asset)】
{assets_text[:30000]} 
(素材结束)

【写作约束】
- 语调风格: {tone}
- 目标篇幅: {length}
- 必须基于素材库内容，严禁编造数据。
"""

def get_outline_gen_prompt(requirements: str) -> str:
    return f"""
    任务：基于素材库和用户需求，设计文章结构。
    用户需求："{requirements}"
    
    请输出 JSON 格式的章节列表：
    [
        {{
            "title": "章节标题 (吸引人)",
            "gist": "本章核心写作指令 (50字以内)",
            "estimated_words": 300
        }},
        ...
    ]
    确保逻辑连贯，起承转合。
    """

def get_section_write_prompt(section_title: str, section_gist: str, prev_context: str) -> str:
    return f"""
    任务：撰写章节 【{section_title}】
    
    【本章指引】
    {section_gist}
    
    【前文脉络 (用于衔接)】
    ...{prev_context[-500:]}
    
    请直接撰写本章正文内容（Markdown格式）。
    要求：
    1. 不要在开头重复写章节标题。
    2. 多引用素材中的具体细节、数据或金句。
    3. 这一章写完即可，不要写全文总结。
    """

def get_polishing_prompt(content: str, instruction: str) -> str:
    return f"""
    任务：根据指令修改以下文本。
    
    【原文本】
    {content}
    
    【修改指令】
    {instruction}
    
    请直接输出修改后的文本。
    """