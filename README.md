# EduAssist AI

A final-year-project prototype: an AI-assisted academic monitoring platform for students, parents and faculty.

**Stack:** HTML/CSS/JavaScript - Python FastAPI - SQLite - Pandas/NumPy/scikit-learn.
All data is synthetic sample data.

## Run it

```powershell
cd eduassist-ai
.\run.ps1            # first run installs, trains the model and seeds the database
```
Then open http://127.0.0.1:8000 (API docs at `/docs`).

Manual steps if you prefer:
```powershell
python -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m ml.generate_data; python -m ml.train      # synthetic dataset + model
python -m database.seed                              # sample data + runs the AI pipeline
uvicorn backend.main:app --reload
python -m pytest tests -q                            # 19 API tests
```
Re-running `python -m database.seed` resets all data.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Faculty | faculty1@eduassist.com | faculty123 |
| Student | student1@eduassist.com | student123 |
| Parent (of student1) | parent1@eduassist.com | parent123 |

Students are `student1..60`, parents `parent1..60`, faculty `faculty1..3` (same passwords).

## The six modules

| # | Module | Where | How it works |
|---|---|---|---|
| 1 | Academic Risk Prediction | `ml/`, `services/risk_service.py`, `/risk` | Logistic Regression on 7 features (attendance, marks, marks trend, assignments, LMS activity, failed subjects, previous GPA) -> Low/Medium/High, a 0-100 risk index and the top reasons |
| 2 | AI Early Warning | `services/alert_service.py`, `/alerts` | ML risk + rules (low attendance, attendance drop, absence streak, marks drop, low assignments, failing subjects). Alerts are Critical/Warning/Info, de-duplicated, auto-resolved when the cause clears |
| 3 | Smart Campus Bus Tracking | `services/bus_service.py`, `/bus`, `bus.html` | Simulated GPS: each bus loops its route (15x real speed). Leaflet map, live ETA to every stop |
| 4 | Chatbot (student/parent/faculty) | `services/chatbot_service.py`, `/chatbot` | Regex intents + live database answers, role-aware, TF-IDF FAQ fallback. No external LLM |
| 5 | Faculty Dashboard | `faculty.html`, `/dashboard` | Stats, risk and subject charts, searchable student table, student detail popup, alert resolve, "Run AI Analysis" |
| 6 | Student Progress Score | `services/score_service.py`, `/progress` | `40% marks + 25% attendance + 20% assignments + 10% engagement + 5% improvement trend`, with grade, rank and class average |

Pipeline order: **raw data -> Progress Score + Risk Prediction -> Early Warning alerts -> Dashboard / Chatbot**.
"Run AI Analysis" (`POST /dashboard/refresh`) re-runs the whole pipeline.

## Role-based access
- Student: own data only. Parent: their child's data only. Faculty: everything.
- Enforced on the server (`ensure_can_view_student`, `require_role`), not just hidden in the UI.

## Project layout
```
backend/   FastAPI app: routers/ (HTTP), services/ (logic), models.py, auth.py
ml/        features.py, generate_data.py, train.py, model/risk_model.joblib
database/  seed.py, eduassist.db (generated)
frontend/  index.html (login), student/parent/faculty/bus .html, js/, css/
tests/     test_api.py
```

## Suggested demo script (5 minutes)
1. **Login as faculty.** Dashboard shows class stats and the risk chart. Point out the High-risk students at the top of the table.
2. Click a High-risk student: the "Why flagged" reasons and alerts explain the prediction.
3. Resolve an alert, then click **Run AI Analysis** to show the pipeline re-running.
4. Open the chatbot: "Which students are at risk?", "Who has low attendance?", "Tell me about 21CS003".
5. **Logout, login as student.** Show the progress score breakdown, risk factors, alerts. Ask the chatbot "What is my progress score?".
6. Open **Bus Tracking**: the bus moves on the map and ETAs count down.
7. **Login as parent**: same data about their child. Try opening `faculty.html` - access is blocked.

## Honest limitations (mention these in your report)
- Training labels are **synthetic**. The ~92% accuracy shows the pipeline works, not real-world performance. With real data you would retrain with `python -m ml.train`.
- Bus positions are **simulated**. A real system would receive GPS pings from a device on the bus.
- The chatbot is rule-based. It only understands the intents it was built for, but it needs no internet or API key.
- Auth is prototype-grade (JWT with a hard-coded secret in `backend/auth.py`). Change it before any real deployment.
- Bus map tiles and Chart.js load from CDNs, so those need internet access.

## Possible future work
Real GPS feed, LLM-backed chatbot, SMS/email alerts, model retraining on real data, per-semester history charts.
