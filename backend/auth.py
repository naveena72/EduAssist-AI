from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db

SECRET_KEY = "eduassist-prototype-secret-change-me"  # prototype only
ALGORITHM = "HS256"
TOKEN_HOURS = 8

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def create_token(user: models.User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def to_user_out(user: models.User, db: Session) -> schemas.UserOut:
    student_id = None
    if user.role == "student":
        s = db.query(models.Student).filter_by(user_id=user.id).first()
    elif user.role == "parent":
        s = db.query(models.Student).filter_by(parent_user_id=user.id).first()
    else:
        s = None
    if s:
        student_id = s.id
    return schemas.UserOut(id=user.id, name=user.name, email=user.email,
                           role=user.role, student_id=student_id)


def get_current_user(token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> models.User:
    err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                        headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = db.get(models.User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise err
    if user is None:
        raise err
    return user


def ensure_can_view_student(user: models.User, student_id: int, db: Session) -> models.Student:
    """Faculty see everyone; students only themselves; parents only their child."""
    student = db.get(models.Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    allowed = (
        user.role == "faculty"
        or (user.role == "student" and student.user_id == user.id)
        or (user.role == "parent" and student.parent_user_id == user.id)
    )
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot view this student")
    return student


def require_role(*roles: str):
    """Dependency factory: allow only the given roles."""
    def checker(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for your role")
        return user
    return checker
