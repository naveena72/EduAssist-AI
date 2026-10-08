"""Module 1: Academic Risk Prediction.

Builds the model's input features from the database, runs the saved model and
explains the result with the factors pushing the student's risk up.
"""
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .. import models
from ml.features import FEATURE_LABELS

MODEL_PATH = Path(__file__).resolve().parents[2] / "ml" / "model" / "risk_model.joblib"

# Display units for explanations
_UNITS = {"attendance_pct": "%", "avg_internal_marks": "%", "assignment_rate": "%",
          "marks_trend": " pts", "lms_logins_per_week": "/wk", "failed_subjects": "", "prev_gpa": ""}


@lru_cache(maxsize=1)
def load_model() -> dict:
    if not MODEL_PATH.exists():
        raise RuntimeError("Risk model not found. Run: python -m ml.train")
    return joblib.load(MODEL_PATH)


def build_features(db: Session, student: models.Student) -> dict:
    """Aggregate raw attendance / marks / activity rows into the model's features."""
    sid = student.id
    att = db.query(func.avg(case((models.Attendance.status == "present", 1.0), else_=0.0))) \
        .filter(models.Attendance.student_id == sid).scalar()

    marks = db.query(models.Mark).filter_by(student_id=sid).all()
    pct = lambda m: 100.0 * m.score / m.max_score
    avg_marks = sum(pct(m) for m in marks) / len(marks) if marks else 0.0

    def mean_of(exam):
        vals = [pct(m) for m in marks if m.exam_type == exam]
        return sum(vals) / len(vals) if vals else 0.0

    by_subject: dict[int, list[float]] = {}
    for m in marks:
        by_subject.setdefault(m.subject_id, []).append(pct(m))
    failed = sum(1 for v in by_subject.values() if sum(v) / len(v) < 40)

    act = db.query(models.BehaviorActivity).filter_by(student_id=sid).first()
    assign = 100.0 * act.assignments_submitted / act.assignments_total if act else 0.0

    return {
        "attendance_pct": round(100.0 * (att or 0.0), 1),
        "avg_internal_marks": round(avg_marks, 1),
        "marks_trend": round(mean_of("internal2") - mean_of("internal1"), 1),
        "assignment_rate": round(assign, 1),
        "lms_logins_per_week": act.lms_logins_per_week if act else 0.0,
        "failed_subjects": failed,
        "prev_gpa": student.prev_gpa or 0.0,
    }


def _risk_index(model, row: pd.DataFrame) -> float:
    """Expected risk from the class probabilities: Low ~ 0, Medium ~ 0.5, High ~ 1.
    Used for display and for ranking students (High sorts above Medium)."""
    probs = dict(zip(model.classes_, model.predict_proba(row)[0]))
    return float(probs.get("High", 0) + 0.5 * probs.get("Medium", 0))


# +1: a higher value means more risk; -1: a lower value means more risk.
_RISK_DIRECTION = {"attendance_pct": -1, "avg_internal_marks": -1, "marks_trend": -1,
                   "assignment_rate": -1, "lms_logins_per_week": -1,
                   "failed_subjects": +1, "prev_gpa": -1}


def explain(bundle: dict, feats: dict, top_n: int = 3) -> list[dict]:
    """Rank the features by how far the student is on the 'risky' side of the
    training average, weighted by the model's global feature importance.
    (Perturbing single features does not work for students the model is already
    100% sure about, so this score is used instead.)"""
    means, stds, imp = bundle["train_means"], bundle["train_stds"], bundle["importance"]
    out = []
    for f in bundle["features"]:
        z = _RISK_DIRECTION[f] * (feats[f] - means[f]) / (stds[f] or 1.0)
        if z > 0.5:  # clearly worse than typical
            u = _UNITS[f]
            out.append({
                "feature": f,
                "label": FEATURE_LABELS[f],
                "value": feats[f],
                "typical": round(means[f], 1),
                "impact": round(imp[f] * z, 3),
                "message": f"{FEATURE_LABELS[f]} is {feats[f]}{u} (typical {round(means[f], 1)}{u})",
            })
    out.sort(key=lambda d: -d["impact"])
    return out[:top_n]


def predict_student(db: Session, student: models.Student) -> models.RiskPrediction:
    """Run the model for one student and store the result."""
    bundle = load_model()
    feats = build_features(db, student)
    row = pd.DataFrame([feats], columns=bundle["features"])
    model = bundle["model"]
    level = str(model.predict(row)[0])
    pred = models.RiskPrediction(
        student_id=student.id,
        risk_level=level,
        probability=round(_risk_index(model, row), 3),
        top_factors={"features": feats, "factors": explain(bundle, feats) if level != "Low" else []},
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)
    return pred


def latest_predictions(db: Session) -> dict[int, models.RiskPrediction]:
    """Most recent prediction per student."""
    newest = db.query(func.max(models.RiskPrediction.id)).group_by(models.RiskPrediction.student_id)
    rows = db.query(models.RiskPrediction).filter(models.RiskPrediction.id.in_(newest)).all()
    return {r.student_id: r for r in rows}
