"""Train the academic risk model and save it.

Run from project root:  python -m ml.train
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURES, FEATURE_LABELS, LABELS

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "students.csv"
MODEL_PATH = HERE / "model" / "risk_model.joblib"


def main():
    if not DATA.exists():
        raise SystemExit("Dataset missing. Run: python -m ml.generate_data")
    df = pd.read_csv(DATA)
    X, y = df[FEATURES], df["risk_level"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    candidates = {
        "Logistic Regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=1000)),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=8, random_state=42, class_weight="balanced"),
    }

    results = {}
    for name, model in candidates.items():
        cv = cross_val_score(model, X_tr, y_tr, cv=5, scoring="f1_macro").mean()
        model.fit(X_tr, y_tr)
        pred = model.predict(X_te)
        f1 = f1_score(y_te, pred, average="macro")
        results[name] = (model, f1)
        print(f"{name:20s} CV F1={cv:.3f}  Test F1={f1:.3f}  Test acc={np.mean(pred == y_te):.3f}")

    best_name = max(results, key=lambda k: results[k][1])
    best = results[best_name][0]
    print(f"\nBest model: {best_name}\n")
    pred = best.predict(X_te)
    print(classification_report(y_te, pred, labels=LABELS, digits=3))
    print("Confusion matrix (rows=actual, cols=predicted; order Low/Medium/High):")
    print(pd.DataFrame(confusion_matrix(y_te, pred, labels=LABELS), index=LABELS, columns=LABELS))

    # Global feature importance (RF importances, or |coef| for logistic regression)
    if best_name == "Random Forest":
        imp = best.feature_importances_
    else:
        imp = np.abs(best[-1].coef_).mean(axis=0)
        imp = imp / imp.sum()
    print("\nFeature importance:")
    for f, v in sorted(zip(FEATURES, imp), key=lambda t: -t[1]):
        print(f"  {FEATURE_LABELS[f]:24s} {v:.3f}")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": best,
        "name": best_name,
        "features": FEATURES,
        "importance": dict(zip(FEATURES, map(float, imp))),
        "train_means": X_tr.mean().to_dict(),
        "train_stds": X_tr.std().to_dict(),
    }, MODEL_PATH)
    print(f"\nSaved model -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
