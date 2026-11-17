from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": user.id,
        "role": user.role,
        "aud": s.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(claims, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm], audience=s.jwt_audience)
    except jwt.PyJWTError:
        return None


def user_from_token(db: Session, token: str) -> User | None:
    claims = decode_token(token)
    return db.get(User, claims["sub"]) if claims else None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user = user_from_token(db, token)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user
