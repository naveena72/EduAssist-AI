from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..auth import ensure_can_view_student, get_current_user, require_role
from ..database import get_db
from ..services import student_service

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("", dependencies=[Depends(require_role("faculty"))])
def list_students(section: str | None = None, search: str | None = None,
                  db: Session = Depends(get_db)):
    q = db.query(models.Student)
    if section:
        q = q.filter(models.Student.section == section)
    if search:
        like = f"%{search}%"
        q = q.filter(models.Student.name.ilike(like) | models.Student.roll_no.ilike(like))
    return [{"id": s.id, "roll_no": s.roll_no, "name": s.name, "section": s.section,
             "department": s.department, "year": s.year} for s in q.order_by(models.Student.roll_no)]


@router.get("/{student_id}")
def student_detail(student_id: int, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    student = ensure_can_view_student(user, student_id, db)
    return student_service.student_detail(db, student)
