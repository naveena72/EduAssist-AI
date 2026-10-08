"""Builds the full per-student view used by the student/parent pages, the faculty
detail modal and the chatbot."""
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .. import models
from . import alert_service, bus_service, risk_service, score_service

EXAMS = ("internal1", "internal2", "model", "assignment")


def latest_risk(db: Session, student: models.Student) -> models.RiskPrediction:
    pred = (db.query(models.RiskPrediction).filter_by(student_id=student.id)
            .order_by(models.RiskPrediction.id.desc()).first())
    return pred or risk_service.predict_student(db, student)


def risk_dict(pred: models.RiskPrediction) -> dict:
    return {
        "risk_level": pred.risk_level, "probability": pred.probability,
        "features": pred.top_factors["features"], "factors": pred.top_factors["factors"],
        "created_at": pred.created_at.isoformat(timespec="seconds"),
    }


def open_alerts(db: Session, student: models.Student) -> list[dict]:
    rows = db.query(models.Alert).filter_by(student_id=student.id, status="open").all()
    rows.sort(key=lambda a: alert_service.SEVERITY_ORDER.get(a.severity, 9))
    return [alert_service.alert_dict(a, student) for a in rows]


def student_detail(db: Session, student: models.Student) -> dict:
    sid = student.id
    subjects = db.query(models.Subject).order_by(models.Subject.id).all()

    att = dict(db.query(
        models.Attendance.subject_id,
        func.avg(case((models.Attendance.status == "present", 100.0), else_=0.0)),
    ).filter(models.Attendance.student_id == sid).group_by(models.Attendance.subject_id).all())

    marks: dict[int, dict[str, float]] = {}
    for m in db.query(models.Mark).filter_by(student_id=sid):
        marks.setdefault(m.subject_id, {})[m.exam_type] = round(100 * m.score / m.max_score, 1)

    by_subject_att, by_subject_marks = [], []
    for s in subjects:
        by_subject_att.append({"subject": s.name, "code": s.code, "pct": round(att.get(s.id, 0), 1)})
        row = marks.get(s.id, {})
        vals = [row[e] for e in EXAMS if e in row]
        by_subject_marks.append({"subject": s.name, "code": s.code, **{e: row.get(e) for e in EXAMS},
                                 "average": round(sum(vals) / len(vals), 1) if vals else None})

    feats = risk_service.build_features(db, student)
    act = db.query(models.BehaviorActivity).filter_by(student_id=sid).first()
    bus = db.get(models.Bus, student.bus_id) if student.bus_id else None

    return {
        "student": {"id": sid, "roll_no": student.roll_no, "name": student.name,
                    "department": student.department, "year": student.year,
                    "section": student.section, "prev_gpa": student.prev_gpa},
        "attendance": {"overall": feats["attendance_pct"], "by_subject": by_subject_att},
        "marks": {"overall": feats["avg_internal_marks"], "trend": feats["marks_trend"],
                  "failed_subjects": feats["failed_subjects"], "by_subject": by_subject_marks},
        "activity": {
            "assignments_submitted": act.assignments_submitted if act else 0,
            "assignments_total": act.assignments_total if act else 0,
            "lms_logins_per_week": act.lms_logins_per_week if act else 0,
            "extracurricular_count": act.extracurricular_count if act else 0,
        },
        "risk": risk_dict(latest_risk(db, student)),
        "progress": score_service.progress_detail(db, student),
        "alerts": open_alerts(db, student),
        "bus": {"id": bus.id, "bus_no": bus.bus_no, "route": bus.route.name,
                "driver_name": bus.driver_name, "driver_phone": bus.driver_phone} if bus else None,
    }
