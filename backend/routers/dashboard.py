from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .. import models
from ..auth import require_role
from ..database import get_db
from ..services import analytics_service, risk_service, score_service

router = APIRouter(prefix="/dashboard", tags=["Faculty Dashboard"],
                   dependencies=[Depends(require_role("faculty"))])


def _risk_counts(db: Session) -> dict:
    counts = {"Low": 0, "Medium": 0, "High": 0}
    for p in risk_service.latest_predictions(db).values():
        counts[p.risk_level] += 1
    return counts


@router.post("/refresh")
def refresh(db: Session = Depends(get_db)):
    """Run the full AI pipeline: risk -> progress score -> alerts."""
    return analytics_service.refresh_all(db)


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    preds = risk_service.latest_predictions(db)
    scores = score_service.latest_scores(db)
    feats = [p.top_factors["features"] for p in preds.values()]
    avg = lambda key: round(sum(f[key] for f in feats) / len(feats), 1) if feats else 0
    alerts = db.query(models.Alert).filter_by(status="open")
    return {
        "total_students": db.query(models.Student).count(),
        "risk": _risk_counts(db),
        "avg_attendance": avg("attendance_pct"),
        "avg_marks": avg("avg_internal_marks"),
        "avg_progress_score": round(sum(s.score for s in scores.values()) / len(scores), 1) if scores else 0,
        "open_alerts": alerts.count(),
        "critical_alerts": alerts.filter_by(severity="Critical").count(),
        "analysed": len(preds) > 0,
    }


@router.get("/risk-distribution")
def risk_distribution(db: Session = Depends(get_db)):
    counts = _risk_counts(db)
    return {"labels": list(counts), "counts": list(counts.values())}


@router.get("/class-performance")
def class_performance(db: Session = Depends(get_db)):
    marks = dict(db.query(models.Mark.subject_id, func.avg(100.0 * models.Mark.score / models.Mark.max_score))
                 .group_by(models.Mark.subject_id).all())
    att = dict(db.query(models.Attendance.subject_id,
                        func.avg(case((models.Attendance.status == "present", 100.0), else_=0.0)))
               .group_by(models.Attendance.subject_id).all())
    return [{"subject": s.name, "code": s.code,
             "avg_marks_pct": round(marks.get(s.id, 0), 1),
             "avg_attendance_pct": round(att.get(s.id, 0), 1)}
            for s in db.query(models.Subject).order_by(models.Subject.id)]


@router.get("/students")
def student_table(db: Session = Depends(get_db)):
    """One row per student for the dashboard table (highest risk first)."""
    preds = risk_service.latest_predictions(db)
    scores = score_service.latest_scores(db)
    alert_counts = dict(db.query(models.Alert.student_id, func.count())
                        .filter_by(status="open").group_by(models.Alert.student_id).all())
    rows = []
    for s in db.query(models.Student).order_by(models.Student.roll_no):
        p, sc = preds.get(s.id), scores.get(s.id)
        f = p.top_factors["features"] if p else {}
        rows.append({
            "id": s.id, "roll_no": s.roll_no, "name": s.name, "section": s.section,
            "attendance": f.get("attendance_pct"), "marks": f.get("avg_internal_marks"),
            "progress_score": sc.score if sc else None, "grade": sc.grade if sc else None,
            "risk_level": p.risk_level if p else None, "risk_probability": p.probability if p else None,
            "open_alerts": alert_counts.get(s.id, 0),
        })
    rows.sort(key=lambda r: -(r["risk_probability"] or 0))
    return rows
