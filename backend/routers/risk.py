from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import ensure_can_view_student, get_current_user, require_role
from ..database import get_db
from ..services import risk_service

router = APIRouter(prefix="/risk", tags=["Risk Prediction"])


def _out(pred: models.RiskPrediction, student: models.Student) -> schemas.RiskOut:
    return schemas.RiskOut(
        student_id=student.id, roll_no=student.roll_no, name=student.name,
        risk_level=pred.risk_level, probability=pred.probability,
        features=pred.top_factors["features"], factors=pred.top_factors["factors"],
        created_at=pred.created_at.isoformat(timespec="seconds"),
    )


@router.post("/predict-all", dependencies=[Depends(require_role("faculty"))])
def predict_all(db: Session = Depends(get_db)):
    """Refresh predictions for every student."""
    counts = {"Low": 0, "Medium": 0, "High": 0}
    for s in db.query(models.Student).all():
        counts[risk_service.predict_student(db, s).risk_level] += 1
    return {"students": sum(counts.values()), "distribution": counts}


@router.get("", response_model=list[schemas.RiskOut], dependencies=[Depends(require_role("faculty"))])
def list_risk(level: str | None = None, db: Session = Depends(get_db)):
    """Latest prediction for every student, highest risk first. Optional ?level=High."""
    latest = risk_service.latest_predictions(db)
    students = {s.id: s for s in db.query(models.Student).all()}
    rows = [_out(p, students[sid]) for sid, p in latest.items()]
    if level:
        rows = [r for r in rows if r.risk_level.lower() == level.lower()]
    return sorted(rows, key=lambda r: -r.probability)


@router.post("/predict/{student_id}", response_model=schemas.RiskOut,
             dependencies=[Depends(require_role("faculty"))])
def predict_one(student_id: int, db: Session = Depends(get_db)):
    student = db.get(models.Student, student_id)
    if student is None:
        raise HTTPException(404, "Student not found")
    return _out(risk_service.predict_student(db, student), student)


@router.get("/{student_id}", response_model=schemas.RiskOut)
def get_risk(student_id: int, user: models.User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    student = ensure_can_view_student(user, student_id, db)
    pred = (db.query(models.RiskPrediction).filter_by(student_id=student_id)
            .order_by(models.RiskPrediction.id.desc()).first())
    if pred is None:  # not predicted yet: compute on demand
        pred = risk_service.predict_student(db, student)
    return _out(pred, student)
