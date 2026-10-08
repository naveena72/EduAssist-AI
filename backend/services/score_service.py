"""Module 6: Student Progress Score (weighted formula, 0-100)."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from .risk_service import build_features

# Configurable weights (must sum to 1.0)
WEIGHTS = {"marks": 0.40, "attendance": 0.25, "assignments": 0.20,
           "engagement": 0.10, "improvement": 0.05}
LABELS = {"marks": "Marks", "attendance": "Attendance", "assignments": "Assignments",
          "engagement": "Engagement", "improvement": "Improvement trend"}


def grade_for(score: float) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 65:
        return "Good"
    if score >= 50:
        return "Average"
    return "Needs Improvement"


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def compute_progress(db: Session, student: models.Student) -> models.ProgressScore:
    f = build_features(db, student)
    act = db.query(models.BehaviorActivity).filter_by(student_id=student.id).first()
    extra = min(act.extracurricular_count, 3) / 3 * 100 if act else 0.0
    values = {
        "marks": f["avg_internal_marks"],
        "attendance": f["attendance_pct"],
        "assignments": f["assignment_rate"],
        "engagement": 0.7 * _clip(f["lms_logins_per_week"] / 8 * 100) + 0.3 * extra,
        "improvement": _clip(50 + 2.5 * f["marks_trend"]),  # 0 trend = 50, +20 pts = 100
    }
    components = {
        k: {"label": LABELS[k], "value": round(v, 1), "weight": WEIGHTS[k],
            "points": round(v * WEIGHTS[k], 1)}
        for k, v in values.items()
    }
    score = round(sum(WEIGHTS[k] * v for k, v in values.items()), 1)
    row = models.ProgressScore(student_id=student.id, score=score, grade=grade_for(score),
                               breakdown=components)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def latest_scores(db: Session) -> dict[int, models.ProgressScore]:
    newest = db.query(func.max(models.ProgressScore.id)).group_by(models.ProgressScore.student_id)
    rows = db.query(models.ProgressScore).filter(models.ProgressScore.id.in_(newest)).all()
    return {r.student_id: r for r in rows}


def progress_detail(db: Session, student: models.Student) -> dict:
    """Latest score (computed on demand) plus class rank and class average."""
    scores = latest_scores(db)
    row = scores.get(student.id) or compute_progress(db, student)
    scores[student.id] = row
    ranked = sorted(scores.values(), key=lambda r: -r.score)
    rank = next(i for i, r in enumerate(ranked, 1) if r.student_id == student.id)
    return {
        "score": row.score, "grade": row.grade, "components": row.breakdown,
        "rank": rank, "total_students": len(ranked),
        "class_average": round(sum(r.score for r in ranked) / len(ranked), 1),
        "computed_at": row.computed_at.isoformat(timespec="seconds"),
    }
