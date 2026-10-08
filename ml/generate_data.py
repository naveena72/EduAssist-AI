"""Generate a synthetic student dataset for training the risk model.

Run from project root:  python -m ml.generate_data
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURES

OUT = Path(__file__).resolve().parent / "data" / "students.csv"
N = 1500


def generate(n: int = N, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # Latent academic strength drives all features, so they correlate like real data.
    strength = rng.normal(0, 1, n)

    attendance = np.clip(80 + 11 * strength + rng.normal(0, 6, n), 35, 100)
    marks = np.clip(62 + 15 * strength + rng.normal(0, 7, n), 8, 98)
    trend = np.clip(2 * strength + rng.normal(0, 7, n), -30, 30)
    assignment = np.clip(80 + 14 * strength + rng.normal(0, 10, n), 0, 100)
    lms = np.clip(5 + 2.2 * strength + rng.normal(0, 1.5, n), 0, 15)
    gpa = np.clip(7 + 1.3 * strength + rng.normal(0, 0.5, n), 3, 10)
    failed = np.clip(np.round((45 - marks) / 8 + rng.normal(0, 0.7, n)), 0, 5)

    df = pd.DataFrame({
        "attendance_pct": attendance.round(1),
        "avg_internal_marks": marks.round(1),
        "marks_trend": trend.round(1),
        "assignment_rate": assignment.round(1),
        "lms_logins_per_week": lms.round(1),
        "failed_subjects": failed.astype(int),
        "prev_gpa": gpa.round(2),
    })

    # Risk score: higher = more at risk. Weights mirror what faculty look at.
    # Label noise is added so the task is not trivially perfect.
    risk = (
        0.30 * (100 - df.attendance_pct)
        + 0.30 * (100 - df.avg_internal_marks)
        + 0.15 * (-df.marks_trend).clip(lower=0)
        + 0.10 * (100 - df.assignment_rate)
        + 2.0 * df.failed_subjects
        + 1.5 * (10 - df.prev_gpa)
        + rng.normal(0, 2.5, n)
    )
    df["risk_score"] = risk.round(2)
    lo, hi = np.percentile(risk, [55, 82])  # ~55% Low, ~27% Medium, ~18% High
    df["risk_level"] = np.where(risk < lo, "Low", np.where(risk < hi, "Medium", "High"))
    return df[FEATURES + ["risk_score", "risk_level"]]


if __name__ == "__main__":
    df = generate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"Saved {len(df)} rows -> {OUT}")
    print(df.risk_level.value_counts().to_string())
    print(df.groupby("risk_level")[FEATURES].mean().round(1).to_string())
