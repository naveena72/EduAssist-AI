"""Module 4: EduAssist chatbot for students, parents and faculty.

Rule-based: regex intent detection + live database lookups, with TF-IDF matching over
the FAQ table as a fallback. No external LLM or internet connection is needed.
"""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from .. import models
from . import bus_service, risk_service, score_service, student_service

SUGGESTIONS = {
    "student": ["What is my attendance?", "Show my marks", "What is my progress score?",
                "Am I at risk?", "Any alerts for me?", "Where is my bus?"],
    "parent": ["What is my child's attendance?", "How are my child's marks?",
               "Is my child at risk?", "Any alerts?", "When will the bus arrive?"],
    "faculty": ["Which students are at risk?", "Who has low attendance?", "Class summary",
                "Top performers", "Tell me about 21CS001", "Where are the buses?"],
}

# Order matters: the first matching pattern wins.
INTENTS = [
    ("greeting", r"^\s*(hi|hello|hey|good (morning|afternoon|evening))\b"),
    ("thanks", r"\b(thanks|thank you|thx)\b"),
    ("help", r"\b(help|what can you do|options|menu)\b"),
    ("faq_calc", r"calculat|formula|how (is|are|do) .*(computed|worked|scored)"),
    ("at_risk_list", r"(at[- ]?risk|high[- ]?risk|risky|struggling|weak).*students?|students?.*(at[- ]?risk|high[- ]?risk|struggling)|who.*(risk|fail)"),
    ("low_attendance_list", r"(who|which|list|students?).*(low|poor|short|below).*attend|attend.*(shortage|below 75)"),
    ("top_list", r"top (performers?|students?)|best students?|toppers?|leaderboard"),
    ("class_summary", r"class (summary|overview|performance|average)|summary|overview|statistics|dashboard"),
    ("attendance", r"attend|present|absent|bunk"),
    ("progress", r"progress|performance|how (am i|is my (child|son|daughter)) doing|rank"),
    ("marks", r"\bmarks?\b|grades?|result|internal|exam|gpa|cgpa"),
    ("risk", r"risk|danger|fail|safe|pass\b"),
    ("alerts", r"alert|warning|notif|issue|problem|concern"),
    ("bus", r"\bbus(es)?\b|\beta\b|arriv|route|driver|transport|pick ?up"),
]
PER_STUDENT = {"attendance", "progress", "marks", "risk", "alerts", "bus"}
ROLL_RE = re.compile(r"\b(\d{2}cs\d{3})\b", re.I)


def _detect(msg: str) -> str | None:
    for name, pattern in INTENTS:
        if re.search(pattern, msg, re.I):
            return name
    return None


def _linked_student(db: Session, user: models.User) -> models.Student | None:
    if user.role == "student":
        return db.query(models.Student).filter_by(user_id=user.id).first()
    if user.role == "parent":
        return db.query(models.Student).filter_by(parent_user_id=user.id).first()
    return None


def _find_student(db: Session, text: str) -> models.Student | None:
    m = ROLL_RE.search(text)
    if m:
        return db.query(models.Student).filter(models.Student.roll_no.ilike(m.group(1))).first()
    low = text.lower()
    for s in db.query(models.Student).all():
        if s.name.lower() in low:
            return s
    return None


def _faq(db: Session, role: str, msg: str, threshold: float) -> str | None:
    faqs = db.query(models.FAQ).filter(models.FAQ.audience.in_([role, "all"])).all()
    if not faqs:
        return None
    vec = TfidfVectorizer(stop_words="english").fit([f.question for f in faqs] + [msg])
    sims = cosine_similarity(vec.transform([msg]), vec.transform([f.question for f in faqs]))[0]
    best = int(sims.argmax())
    return faqs[best].answer if sims[best] >= threshold else None


# ---------- per-student answers ----------
def _student_answer(db: Session, intent: str, student: models.Student, poss: str) -> str:
    d = student_service.student_detail(db, student)
    if intent == "attendance":
        a = d["attendance"]
        verdict = "above" if a["overall"] >= 75 else "BELOW"
        lines = [f"{poss} overall attendance is {a['overall']}% ({verdict} the 75% requirement)."]
        lines += [f"  - {s['subject']}: {s['pct']}%" for s in a["by_subject"]]
        return "\n".join(lines)
    if intent == "marks":
        m = d["marks"]
        lines = [f"{poss} average marks are {m['overall']}% "
                 f"({'improving' if m['trend'] > 1 else 'declining' if m['trend'] < -1 else 'steady'} "
                 f"trend, {m['trend']:+} pts from Internal 1 to 2)."]
        lines += [f"  - {s['subject']}: {s['average']}%" for s in m["by_subject"]]
        if m["failed_subjects"]:
            lines.append(f"Below 40% in {m['failed_subjects']} subject(s) - needs attention.")
        return "\n".join(lines)
    if intent == "progress":
        p = d["progress"]
        lines = [f"{poss} progress score is {p['score']}/100 ({p['grade']}). "
                 f"Rank {p['rank']} of {p['total_students']}; class average {p['class_average']}."]
        lines += [f"  - {c['label']}: {c['value']} (weight {int(c['weight'] * 100)}%)"
                  for c in p["components"].values()]
        return "\n".join(lines)
    if intent == "risk":
        r = d["risk"]
        text = f"{poss} academic risk level is {r['risk_level']} (risk index {round(r['probability'] * 100)}/100)."
        if r["factors"]:
            text += "\nMain reasons:\n" + "\n".join(f"  - {f['message']}" for f in r["factors"])
        elif r["risk_level"] == "Low":
            text += " Keep up the good work!"
        return text
    if intent == "alerts":
        if not d["alerts"]:
            return "There are no open alerts. Everything looks fine."
        return f"{len(d['alerts'])} open alert(s):\n" + "\n".join(
            f"  - [{a['severity']}] {a['message']}" for a in d["alerts"])
    if intent == "bus":
        if not d["bus"]:
            return "No bus is assigned (not a campus bus user)."
        bus = db.get(models.Bus, d["bus"]["id"])
        st = bus_service.bus_status(db, bus)
        where = ("has arrived at campus" if st["eta_to_campus_min"] is None else
                 f"is on the way, next stop {st['next_stop']}, about {st['eta_to_campus_min']} min to campus")
        return (f"Bus {st['bus_no']} ({st['route']}) {where}. "
                f"Driver: {st['driver_name']} ({st['driver_phone']}). Open 'Bus Tracking' for the live map.")
    return ""


# ---------- faculty aggregate answers ----------
def _faculty_list(db: Session, intent: str) -> str:
    students = {s.id: s for s in db.query(models.Student).all()}
    if intent == "at_risk_list":
        preds = [p for p in risk_service.latest_predictions(db).values() if p.risk_level == "High"]
        preds.sort(key=lambda p: -p.probability)
        if not preds:
            return "No students are currently predicted as High risk."
        lines = [f"{len(preds)} student(s) at High risk:"]
        for p in preds[:8]:
            s = students[p.student_id]
            why = p.top_factors["factors"][0]["message"] if p.top_factors["factors"] else ""
            lines.append(f"  - {s.roll_no} {s.name}: {why}")
        if len(preds) > 8:
            lines.append(f"  ...and {len(preds) - 8} more (see the dashboard).")
        return "\n".join(lines)
    if intent == "low_attendance_list":
        rows = []
        for p in risk_service.latest_predictions(db).values():
            att = p.top_factors["features"]["attendance_pct"]
            if att < 75:
                rows.append((att, students[p.student_id]))
        rows.sort(key=lambda t: t[0])
        if not rows:
            return "Every student has at least 75% attendance."
        lines = [f"{len(rows)} student(s) below 75% attendance:"]
        lines += [f"  - {s.roll_no} {s.name}: {att}%" for att, s in rows[:8]]
        if len(rows) > 8:
            lines.append(f"  ...and {len(rows) - 8} more.")
        return "\n".join(lines)
    if intent == "top_list":
        scores = sorted(score_service.latest_scores(db).values(), key=lambda r: -r.score)[:5]
        if not scores:
            return "Progress scores have not been calculated yet. Click 'Run AI Analysis' on the dashboard."
        return "Top 5 by progress score:\n" + "\n".join(
            f"  {i}. {students[r.student_id].roll_no} {students[r.student_id].name}: {r.score} ({r.grade})"
            for i, r in enumerate(scores, 1))
    if intent == "class_summary":
        preds = risk_service.latest_predictions(db).values()
        scores = score_service.latest_scores(db).values()
        dist = {"Low": 0, "Medium": 0, "High": 0}
        for p in preds:
            dist[p.risk_level] += 1
        open_alerts = db.query(models.Alert).filter_by(status="open").count()
        crit = db.query(models.Alert).filter_by(status="open", severity="Critical").count()
        avg = round(sum(r.score for r in scores) / len(scores), 1) if scores else "n/a"
        return (f"Class summary: {len(students)} students. Risk - Low {dist['Low']}, Medium {dist['Medium']}, "
                f"High {dist['High']}. Average progress score {avg}. "
                f"{open_alerts} open alerts ({crit} critical).")
    return ""


def _faculty_bus(db: Session) -> str:
    lines = []
    for b in db.query(models.Bus).all():
        st = bus_service.bus_status(db, b)
        if st["eta_to_campus_min"] is None:
            lines.append(f"  - {st['bus_no']} ({st['route']}): arrived at campus")
        else:
            lines.append(f"  - {st['bus_no']} ({st['route']}): next stop {st['next_stop']}, "
                         f"{st['eta_to_campus_min']} min to campus")
    return "Live bus status:\n" + "\n".join(lines)


# ---------- main entry ----------
def answer(db: Session, user: models.User, message: str) -> dict:
    role = user.role
    msg = message.strip()
    intent = _detect(msg)
    suggestions = SUGGESTIONS[role]
    text = None

    if intent == "greeting":
        text = f"Hello {user.name.split()[0]}! I'm EduAssist AI. Ask me about " + {
            "student": "your attendance, marks, progress, risk, alerts or bus.",
            "parent": "your child's attendance, marks, progress, risk, alerts or bus.",
            "faculty": "at-risk students, attendance, class summary or any student by roll number.",
        }[role]
    elif intent == "thanks":
        text = "You're welcome! Let me know if you need anything else."
    elif intent == "help":
        text = "I can answer questions about: " + "; ".join(suggestions) + "."
    elif intent == "faq_calc":
        text = _faq(db, role, msg, 0.05)

    elif role == "faculty":
        if intent in ("at_risk_list", "low_attendance_list", "top_list", "class_summary"):
            text = _faculty_list(db, intent)
        else:
            target = _find_student(db, msg)
            if intent in PER_STUDENT and target:
                text = _student_answer(db, intent, target, f"{target.name}'s")
            elif intent == "bus":
                text = _faculty_bus(db)
            elif intent == "progress":
                text = _faculty_list(db, "top_list")
            elif intent in PER_STUDENT:
                text = "Which student? Please include a roll number such as 21CS001."
            elif target:  # only a student was named: give an overview
                text = _student_answer(db, "progress", target, f"{target.name}'s") + "\n\n" + \
                    _student_answer(db, "risk", target, f"{target.name}'s")
                intent = "student_overview"
    else:
        student = _linked_student(db, user)
        if intent in PER_STUDENT:
            if student is None:
                text = "No student record is linked to your account."
            else:
                poss = "Your" if role == "student" else f"{student.name}'s"
                text = _student_answer(db, intent, student, poss)
        elif intent in ("at_risk_list", "low_attendance_list", "top_list", "class_summary"):
            text = "That information is only available to faculty."

    if text is None:  # fallback: FAQ similarity, then a help message
        faq = _faq(db, role, msg, 0.3)
        if faq:
            text, intent = faq, "faq"
        else:
            intent = intent or "unknown"
            text = "Sorry, I didn't understand that. Try: " + "; ".join(suggestions[:4]) + "."

    db.add(models.ChatLog(user_id=user.id, role=role, question=msg, answer=text, intent=intent))
    db.commit()
    return {"answer": text, "intent": intent, "suggestions": suggestions}
