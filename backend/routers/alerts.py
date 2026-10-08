from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user, require_role
from ..database import get_db
from ..services import alert_service
from ..services.chatbot_service import _linked_student

router = APIRouter(prefix="/alerts", tags=["Early Warning"])


@router.get("")
def list_alerts(severity: str | None = None, status: str | None = "open",
                student_id: int | None = None,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Faculty see all alerts; a student or parent sees only their own student's."""
    q = db.query(models.Alert)
    if user.role != "faculty":
        own = _linked_student(db, user)
        q = q.filter(models.Alert.student_id == (own.id if own else -1))
    elif student_id:
        q = q.filter(models.Alert.student_id == student_id)
    if severity:
        q = q.filter(models.Alert.severity.ilike(severity))
    if status and status != "all":
        q = q.filter(models.Alert.status == status)
    students = {s.id: s for s in db.query(models.Student).all()}
    rows = [alert_service.alert_dict(a, students[a.student_id]) for a in q]
    rows.sort(key=lambda a: (alert_service.SEVERITY_ORDER.get(a["severity"], 9), -a["id"]))
    return rows


@router.post("/generate", dependencies=[Depends(require_role("faculty"))])
def generate(db: Session = Depends(get_db)):
    """Re-run the early-warning rules (uses the latest risk predictions)."""
    return alert_service.generate_alerts(db)


@router.patch("/{alert_id}/resolve", dependencies=[Depends(require_role("faculty"))])
def resolve(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(models.Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    alert.status = "resolved"
    db.commit()
    return {"id": alert.id, "status": alert.status}
