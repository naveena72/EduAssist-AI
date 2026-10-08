from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..auth import ensure_can_view_student, get_current_user, require_role
from ..database import get_db
from ..services import score_service

router = APIRouter(prefix="/progress", tags=["Progress Score"])


@router.get("", dependencies=[Depends(require_role("faculty"))])
def leaderboard(db: Session = Depends(get_db)):
    """All students ranked by their latest progress score."""
    students = {s.id: s for s in db.query(models.Student).all()}
    rows = sorted(score_service.latest_scores(db).values(), key=lambda r: -r.score)
    return [{"rank": i, "student_id": r.student_id, "roll_no": students[r.student_id].roll_no,
             "name": students[r.student_id].name, "score": r.score, "grade": r.grade}
            for i, r in enumerate(rows, 1)]


@router.post("/recompute", dependencies=[Depends(require_role("faculty"))])
def recompute(db: Session = Depends(get_db)):
    scores = [score_service.compute_progress(db, s).score for s in db.query(models.Student).all()]
    return {"students": len(scores), "average_score": round(sum(scores) / len(scores), 1)}


@router.get("/{student_id}")
def get_progress(student_id: int, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    student = ensure_can_view_student(user, student_id, db)
    return {"student_id": student.id, "name": student.name, "roll_no": student.roll_no,
            **score_service.progress_detail(db, student)}
