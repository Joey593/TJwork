import hashlib, hmac, secrets, time
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
import jwt
from .config import JWT_SECRET
from .db import Session, User

def hash_password(password):
    salt = secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex()
def verify_password(password, stored):
    salt, expected = stored.split(':')
    actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex()
    return hmac.compare_digest(actual, expected)
def token(user):
    return jwt.encode({'sub':user.id,'iat':int(time.time()),'exp':int(time.time())+8*3600},JWT_SECRET,algorithm='HS256')
bearer = HTTPBearer(auto_error=False)
def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    try:
        if credentials is None: raise ValueError()
        user_id = jwt.decode(credentials.credentials,JWT_SECRET,algorithms=['HS256'])['sub']
        with Session() as db: user = db.get(User, user_id)
        if user is None: raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401,'登录已过期，请重新登录')
def roles(*allowed):
    def check(user=Depends(current_user)):
        if user.role not in allowed: raise HTTPException(403,'当前角色无权执行此操作')
        return user
    return check
writer = roles('admin','reviewer','tester')
reviewer = roles('admin','reviewer')
admin = roles('admin')
