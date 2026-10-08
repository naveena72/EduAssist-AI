"""End-to-end API tests. Needs a seeded database:  python -m database.seed
Run from the project root:  python -m pytest tests -q
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def login(email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="module")
def fac():
    return login("faculty1@eduassist.com", "faculty123")


@pytest.fixture(scope="module")
def stu():
    return login("student1@eduassist.com", "student123")


@pytest.fixture(scope="module")
def par():
    return login("parent1@eduassist.com", "parent123")


# ---- auth
def test_login_and_me(stu):
    me = client.get("/auth/me", headers=stu).json()
    assert me["role"] == "student" and me["student_id"] == 1


def test_swagger_form_login():
    r = client.post("/auth/token", data={"username": "faculty1@eduassist.com", "password": "faculty123"})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"


def test_bad_credentials():
    assert client.post("/auth/login", json={"email": "student1@eduassist.com", "password": "x"}).status_code == 401
    assert client.get("/auth/me").status_code == 401


# ---- access control
def test_student_cannot_see_others(stu, par):
    assert client.get("/students/2", headers=stu).status_code == 403
    assert client.get("/risk/2", headers=par).status_code == 403
    assert client.get("/progress/2", headers=stu).status_code == 403


def test_faculty_only_endpoints(stu, par):
    for path in ("/dashboard/summary", "/risk", "/progress", "/students"):
        assert client.get(path, headers=stu).status_code == 403
        assert client.get(path, headers=par).status_code == 403
    assert client.post("/dashboard/refresh", headers=stu).status_code == 403
    assert client.patch("/alerts/1/resolve", headers=par).status_code == 403


# ---- risk (module 1)
def test_risk_list_sorted(fac):
    rows = client.get("/risk", headers=fac).json()
    assert len(rows) == 60
    probs = [r["probability"] for r in rows]
    assert probs == sorted(probs, reverse=True)
    high = [r for r in rows if r["risk_level"] == "High"]
    assert high and all(r["factors"] for r in high)  # every High student is explained


def test_risk_own(stu, par):
    assert client.get("/risk/1", headers=stu).json()["risk_level"] in ("Low", "Medium", "High")
    assert client.get("/risk/1", headers=par).status_code == 200


# ---- progress score (module 6)
def test_progress_breakdown(stu):
    p = client.get("/progress/1", headers=stu).json()
    assert 0 <= p["score"] <= 100
    comps = p["components"]
    assert abs(sum(c["weight"] for c in comps.values()) - 1.0) < 1e-9
    assert abs(sum(c["points"] for c in comps.values()) - p["score"]) < 0.5
    assert 1 <= p["rank"] <= p["total_students"] == 60


def test_leaderboard(fac):
    rows = client.get("/progress", headers=fac).json()
    assert [r["rank"] for r in rows] == list(range(1, 61))
    assert rows[0]["score"] >= rows[-1]["score"]


# ---- early warning (module 2)
def test_alert_rules_fire(fac):
    alerts = client.get("/alerts?status=open", headers=fac).json()
    types = {a["type"] for a in alerts}
    assert {"risk_ml", "low_attendance", "marks_drop", "absence_streak"} <= types
    sev = [a["severity"] for a in alerts]
    order = {"Critical": 0, "Warning": 1, "Info": 2}
    assert [order[s] for s in sev] == sorted(order[s] for s in sev)  # critical first


def test_alert_visibility_and_resolve(fac, stu):
    mine = client.get("/alerts", headers=stu).json()
    assert all(a["student_id"] == 1 for a in mine)
    a = client.get("/alerts?severity=Info", headers=fac).json()[0]
    assert client.patch(f"/alerts/{a['id']}/resolve", headers=fac).json()["status"] == "resolved"
    gen = client.post("/alerts/generate", headers=fac).json()  # condition persists -> reopened
    assert gen["created"] >= 1


# ---- dashboard (module 5)
def test_dashboard(fac):
    s = client.get("/dashboard/summary", headers=fac).json()
    assert s["total_students"] == 60 and sum(s["risk"].values()) == 60 and s["analysed"]
    d = client.get("/dashboard/risk-distribution", headers=fac).json()
    assert d["labels"] == ["Low", "Medium", "High"] and sum(d["counts"]) == 60
    assert len(client.get("/dashboard/class-performance", headers=fac).json()) == 5
    assert len(client.get("/dashboard/students", headers=fac).json()) == 60


def test_student_detail(stu, fac):
    d = client.get("/students/1", headers=stu).json()
    assert len(d["attendance"]["by_subject"]) == 5 and len(d["marks"]["by_subject"]) == 5
    assert {"risk", "progress", "alerts", "bus"} <= set(d)
    assert client.get("/students/1", headers=fac).status_code == 200
    assert client.get("/students?search=21CS00", headers=fac).json()


# ---- bus (module 3)
def test_bus_tracking(stu):
    buses = client.get("/bus", headers=stu).json()
    assert len(buses) == 3
    b = buses[0]
    assert 12 < b["lat"] < 14 and 79 < b["lng"] < 81
    st = client.get(f"/bus/{b['bus_id']}/status", headers=stu).json()
    etas = [s["eta_min"] for s in st["stops"] if s["eta_min"] is not None]
    assert etas == sorted(etas)  # later stops arrive later
    route = client.get(f"/bus/{b['bus_id']}/route", headers=stu).json()
    assert len(route["stops"]) == 5
    eta = client.get(f"/bus/{b['bus_id']}/eta", headers=stu).json()
    assert eta["stop"] == "Campus"
    assert client.get("/bus/99/status", headers=stu).status_code == 404
    assert client.get("/bus", headers={}).status_code == 401


def test_bus_moves(monkeypatch):
    from backend.database import SessionLocal
    from backend import models
    from backend.services import bus_service
    db = SessionLocal()
    bus = db.get(models.Bus, 1)
    a = bus_service.bus_status(db, bus, now=1000.0, persist=False)
    b = bus_service.bus_status(db, bus, now=1020.0, persist=False)
    assert (a["lat"], a["lng"]) != (b["lat"], b["lng"])
    db.close()


# ---- chatbot (module 4)
def ask(headers, msg):
    r = client.post("/chatbot/ask", json={"message": msg}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_chatbot_student(stu):
    assert ask(stu, "What is my attendance?")["intent"] == "attendance"
    assert "%" in ask(stu, "Show my marks")["answer"]
    assert ask(stu, "what is my progress score")["intent"] == "progress"
    assert ask(stu, "am I at risk?")["intent"] == "risk"
    assert ask(stu, "Where is my bus?")["intent"] in ("bus",)
    assert ask(stu, "any alerts for me?")["intent"] == "alerts"
    assert "40%" in ask(stu, "How is the progress score calculated?")["answer"]
    assert "only available to faculty" in ask(stu, "which students are at risk?")["answer"]
    assert ask(stu, "blah blah xyz")["intent"] == "unknown"


def test_chatbot_parent(par):
    r = ask(par, "What is my child's attendance?")
    assert r["intent"] == "attendance" and "'s overall attendance" in r["answer"]


def test_chatbot_faculty(fac):
    assert "High risk" in ask(fac, "Which students are at risk?")["answer"]
    assert "below 75%" in ask(fac, "Who has low attendance?")["answer"]
    assert "Class summary" in ask(fac, "class summary")["answer"]
    assert "21CS001" in ask(fac, "attendance of 21CS001")["answer"] or "Meera" in ask(fac, "attendance of 21CS001")["answer"]
    assert "Which student" in ask(fac, "what is the attendance")["answer"]
    assert ask(fac, "Top performers")["intent"] == "top_list"


def test_chat_history(stu):
    assert len(client.get("/chatbot/history", headers=stu).json()) > 0
    assert client.post("/chatbot/ask", json={"message": "  "}, headers=stu).status_code == 422
