"""Module 2: AI Early Warning System.

Combines the ML risk prediction with rule-based checks on attendance, marks and
assignments. Each rule yields at most one open alert per student.
"""
from collections import defaultdict

from sqlalchemy.orm import Session

from .. import models
from .risk_service import build_features, latest_predictions

SEVERITY_ORDER = {"Critical": 0, "Warning": 1, "Info": 2}


def _daily_attendance(db: Session, student_id: int) -> list[float]:
    """Fraction of classes attended per day, oldest first."""
    by_day: dict = defaultdict(list)
    rows = db.query(models.Attendance.date, models.Attendance.status) \
        .filter(models.Attendance.student_id == student_id).all()
    for d, status in rows:
        by_day[d].append(1.0 if status == "present" else 0.0)
    return [sum(v) / len(v) for _, v in sorted(by_day.items())]


def _exam_avg(db: Session, student_id: int, exam: str) -> float | None:
    vals = [100 * m.score / m.max_score for m in
            db.query(models.Mark).filter_by(student_id=student_id, exam_type=exam)]
    return sum(vals) / len(vals) if vals else None


def detect(db: Session, student: models.Student, pred: models.RiskPrediction | None) -> dict:
    """Return {alert_type: (severity, message)} for every rule that fires."""
    f = build_features(db, student)
    found: dict[str, tuple[str, str]] = {}

    # 1. ML risk
    if pred and pred.risk_level in ("High", "Medium"):
        reasons = "; ".join(x["message"] for x in pred.top_factors.get("factors", []))
        if pred.risk_level == "High":
            found["risk_ml"] = ("Critical", f"High academic risk predicted. {reasons}".strip())
        else:
            found["risk_ml"] = ("Info", f"Moderate academic risk - keep monitoring. {reasons}".strip())

    # 2. Attendance level
    att = f["attendance_pct"]
    if att < 65:
        found["low_attendance"] = ("Critical", f"Attendance is {att}%, far below the 75% requirement.")
    elif att < 75:
        found["low_attendance"] = ("Warning", f"Attendance is {att}%, below the 75% requirement.")

    # 3. Recent attendance drop and absence streak
    daily = _daily_attendance(db, student.id)
    if len(daily) >= 15:
        recent, earlier = daily[-10:], daily[:-10]
        drop = 100 * (sum(earlier) / len(earlier) - sum(recent) / len(recent))
        if drop >= 15:
            found["attendance_drop"] = (
                "Warning", f"Attendance fell by {drop:.0f} points in the last 10 days.")
    streak = 0
    for frac in reversed(daily):
        if frac < 0.4:
            streak += 1
        else:
            break
    if streak >= 3:
        found["absence_streak"] = (
            "Warning", f"Absent from most classes for the last {streak} days in a row.")

    # 4. Marks decline between internal 1 and internal 2
    i1, i2 = _exam_avg(db, student.id, "internal1"), _exam_avg(db, student.id, "internal2")
    if i1 is not None and i2 is not None and i1 - i2 >= 10:
        sev = "Critical" if i1 - i2 >= 20 else "Warning"
        found["marks_drop"] = (sev, f"Marks dropped from {i1:.0f}% (Internal 1) to {i2:.0f}% (Internal 2).")

    # 5. Assignments
    if f["assignment_rate"] < 50:
        found["low_assignments"] = (
            "Warning", f"Only {f['assignment_rate']:.0f}% of assignments submitted.")

    # 6. Failing subjects
    if f["failed_subjects"] >= 2:
        sev = "Critical" if f["failed_subjects"] >= 3 else "Warning"
        found["failing_subjects"] = (sev, f"Averaging below 40% in {f['failed_subjects']} subjects.")

    return found


def generate_alerts(db: Session) -> dict:
    """Refresh alerts for all students: create new, update existing, auto-resolve cleared."""
    preds = latest_predictions(db)
    created = updated = resolved = 0
    for student in db.query(models.Student).all():
        found = detect(db, student, preds.get(student.id))
        open_alerts = {a.type: a for a in db.query(models.Alert)
                       .filter_by(student_id=student.id, status="open")}
        for typ, (sev, msg) in found.items():
            if typ in open_alerts:
                a = open_alerts[typ]
                if (a.severity, a.message) != (sev, msg):
                    a.severity, a.message = sev, msg
                    updated += 1
            else:
                db.add(models.Alert(student_id=student.id, type=typ, severity=sev, message=msg))
                created += 1
        for typ, a in open_alerts.items():
            if typ not in found:
                a.status = "resolved"
                resolved += 1
    db.commit()
    open_total = db.query(models.Alert).filter_by(status="open").count()
    return {"created": created, "updated": updated, "resolved": resolved, "open_total": open_total}


def alert_dict(a: models.Alert, student: models.Student) -> dict:
    return {
        "id": a.id, "student_id": a.student_id, "roll_no": student.roll_no,
        "student_name": student.name, "type": a.type, "severity": a.severity,
        "message": a.message, "status": a.status,
        "created_at": a.created_at.isoformat(timespec="seconds"),
    }
