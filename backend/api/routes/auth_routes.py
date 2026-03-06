from fastapi import APIRouter, HTTPException, Depends, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

# 配置项
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-666-888")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天

# 用户数据 (演示用，实际应从数据库读取)
# 这里预置一个默认管理员用户: admin / admin123
# 注意：在 Python 3.13 中 bcrypt 可能存在兼容性问题，这里改用 pbkdf2_sha256
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_admin_username():
    """获取管理员用户名（从环境变量读取）"""
    return os.getenv("ADMIN_USERNAME", "admin")

def get_admin_password():
    """获取管理员密码（从环境变量读取）"""
    return os.getenv("ADMIN_PASSWORD", "admin123")

def verify_password(plain_password: str) -> bool:
    """验证密码"""
    admin_password = get_admin_password()
    # 每次验证时重新hash环境变量中的密码进行比较
    # 这样可以确保每次都使用最新的环境变量值
    return pwd_context.verify(plain_password, pwd_context.hash(admin_password))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    if username != get_admin_username():
        raise credentials_exception
    return username

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    admin_username = get_admin_username()
    admin_password = get_admin_password()
    
    if form_data.username != admin_username or form_data.password != admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_users_me(current_user: str = Depends(get_current_user)):
    return {"username": current_user}
