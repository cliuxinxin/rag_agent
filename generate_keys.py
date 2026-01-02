import streamlit_authenticator as stauth
from src.logger import get_logger

logger = get_logger("Key_Generator")

# 在这里定义你想设置的用户名和明文密码
users = ["admin", "user1"]
passwords = ["xianbode", "password123"] # 替换成你想设置的强密码

logger.info("开始生成密码 Hash...")

hashed_passwords = stauth.Hasher(passwords).generate()

for user, hashed in zip(users, hashed_passwords):
    print(f"User: {user}")
    print(f"Hashed: {hashed}")
    logger.info(f"User: {user} - Hash Generated")
    print("-" * 20)
    
logger.info("密码生成完成")