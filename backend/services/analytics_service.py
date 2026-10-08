"""Runs the whole AI pipeline: risk prediction -> progress score -> early-warning alerts."""
from sqlalchemy.orm import Session

from .. import models
from . import alert_service, risk_service, score_service


def refresh_all(db: Session) -> dict:
    students = db.query(models.Student).all()
    distribution = {"Low": 0, "Medium": 0, "High": 0}
    for s in students:
        distribution[risk_service.predict_student(db, s).risk_level] += 1
    scores = [score_service.compute_progress(db, s).score for s in students]
    alerts = alert_service.generate_alerts(db)
    return {
        "students": len(students),
        "risk_distribution": distribution,
        "average_progress_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "alerts": alerts,
    }
