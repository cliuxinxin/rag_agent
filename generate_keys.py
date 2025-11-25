import streamlit_authenticator as stauth

# 在这里定义你想设置的用户名和明文密码
users = ["admin", "user1"]
passwords = ["xianbode", "password123"] # 替换成你想设置的强密码

hashed_passwords = stauth.Hasher(passwords).generate()

for user, hashed in zip(users, hashed_passwords):
    print(f"User: {user}")
    print(f"Hashed: {hashed}")
    print("-" * 20)