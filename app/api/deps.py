"""
Shared FastAPI dependencies: current user resolution and role guards.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.database import get_db
from app.models.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_roles(*roles: UserRole):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker


require_super_admin = require_roles(UserRole.SUPER_ADMIN)
require_college_admin = require_roles(UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN)
require_any_authenticated = require_roles(UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN, UserRole.STUDENT)


def scoped_college_id(user: User = Depends(get_current_user)) -> str | None:
    """Returns the college a COLLEGE_ADMIN is restricted to, or None for SUPER_ADMIN."""
    if user.role == UserRole.COLLEGE_ADMIN:
        return user.college_id
    return None
