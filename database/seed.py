"""Create tables and load sample data.

Run from the project root:  python -m database.seed
"""
import random
from datetime import date, timedelta

import numpy as np

from backend import models
from backend.database import Base, SessionLocal, engine
from backend.security import hash_password

random.seed(42)
np.random.seed(42)

N_STUDENTS = 60
STREAK_STUDENTS = {3, 12, 28}  # absent for the last 4 school days
DROP_STUDENTS = {7, 19, 33}    # internal 2 marks collapse
SUBJECTS = [
    ("Data Structures", "CS201"),
    ("Database Systems", "CS202"),
    ("Operating Systems", "CS203"),
    ("Computer Networks", "CS204"),
    ("Mathematics III", "MA201"),
]
FIRST = ["Aarav", "Diya", "Karthik", "Meera", "Rohan", "Sneha", "Vikram", "Anjali",
         "Arjun", "Priya", "Nikhil", "Divya", "Surya", "Lakshmi", "Harish", "Pooja",
         "Ganesh", "Kavya", "Manoj", "Revathi"]
LAST = ["Kumar", "Raj", "Nair", "Iyer", "Reddy", "Menon", "Pillai", "Sharma", "Das", "Babu"]

# Sample bus routes (coordinates around Chennai)
ROUTES = [
    ("Route A - Tambaram", [("Tambaram", 12.9249, 80.1000), ("Chromepet", 12.9516, 80.1462),
                            ("Pallavaram", 12.9675, 80.1491), ("Guindy", 13.0067, 80.2206),
                            ("Campus", 13.0300, 80.2400)]),
    ("Route B - Anna Nagar", [("Anna Nagar", 13.0850, 80.2101), ("Koyambedu", 13.0694, 80.1948),
                              ("Vadapalani", 13.0500, 80.2121), ("Ashok Nagar", 13.0378, 80.2123),
                              ("Campus", 13.0300, 80.2400)]),
    ("Route C - Velachery", [("Velachery", 12.9815, 80.2180), ("Taramani", 12.9850, 80.2420),
                             ("Adyar", 13.0012, 80.2565), ("Mylapore", 13.0368, 80.2676),
                             ("Campus", 13.0300, 80.2400)]),
]


def main():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()

    # --- Routes & buses
    buses = []
    for i, (rname, stops) in enumerate(ROUTES):
        route = models.Route(name=rname)
        db.add(route)
        db.flush()
        for order, (sname, lat, lng) in enumerate(stops):
            db.add(models.RouteStop(route_id=route.id, stop_name=sname,
                                    lat=lat, lng=lng, stop_order=order))
        bus = models.Bus(bus_no=f"TN-01-B{100 + i}", driver_name=f"Driver {i + 1}",
                         driver_phone=f"98400000{i + 1:02d}", capacity=50, route_id=route.id)
        db.add(bus)
        buses.append(bus)
    db.flush()

    # --- Faculty & subjects
    faculty_rows = []
    for i, (fname, _) in enumerate([("Dr. Ramesh", 0), ("Prof. Sunita", 0), ("Dr. Anand", 0)]):
        u = models.User(name=fname, email=f"faculty{i + 1}@eduassist.com",
                        password_hash=hash_password("faculty123"), role="faculty")
        db.add(u)
        db.flush()
        f = models.Faculty(user_id=u.id, department="CSE")
        db.add(f)
        db.flush()
        faculty_rows.append(f)
    subjects = []
    for i, (sname, code) in enumerate(SUBJECTS):
        s = models.Subject(name=sname, code=code, faculty_id=faculty_rows[i % 3].id)
        db.add(s)
        subjects.append(s)
    db.flush()

    # --- Students, parents, academic data
    days = [date.today() - timedelta(days=d) for d in range(60, 0, -1)
            if (date.today() - timedelta(days=d)).weekday() < 5][:40]
    for n in range(N_STUDENTS):
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        roll = f"21CS{n + 1:03d}"
        su = models.User(name=name, email=f"student{n + 1}@eduassist.com",
                         password_hash=hash_password("student123"), role="student")
        pu = models.User(name=f"Parent of {name}", email=f"parent{n + 1}@eduassist.com",
                         password_hash=hash_password("parent123"), role="parent")
        db.add_all([su, pu])
        db.flush()

        # Hidden "ability" drives correlated, realistic data. ~20% weak, ~25% average.
        ability = np.random.choice(["weak", "average", "strong"], p=[0.2, 0.3, 0.5])
        att_p, mark_mu, sub_rate, lms, gpa = {
            "weak": (0.62, 40, 0.5, 2, 5.2),
            "average": (0.74, 52, 0.7, 3.5, 6.2),
            "strong": (0.93, 80, 0.95, 8, 8.4),
        }[ability]

        student = models.Student(
            user_id=su.id, parent_user_id=pu.id, roll_no=roll, name=name,
            department="CSE", year=2, section="A" if n < 30 else "B",
            prev_gpa=round(float(np.clip(np.random.normal(gpa, 0.5), 4, 10)), 2),
            # first 6 students always ride a bus so the demo logins have one
            bus_id=buses[n % 3].id if n < 6 or random.random() < 0.6 else None,
        )
        db.add(student)
        db.flush()

        for subj in subjects:
            for d in days:
                present = random.random() < np.clip(att_p + np.random.normal(0, 0.05), 0.3, 1)
                if n in STREAK_STUDENTS and d in days[-4:]:
                    present = False  # recent absence streak (early-warning demo)
                db.add(models.Attendance(student_id=student.id, subject_id=subj.id,
                                         date=d, status="present" if present else "absent"))
            for exam, mx in [("internal1", 50), ("internal2", 50), ("model", 100), ("assignment", 20)]:
                pct = np.clip(np.random.normal(mark_mu, 10), 5, 100) / 100
                if exam == "internal2" and n in DROP_STUDENTS:
                    pct *= 0.55  # sudden marks decline (early-warning demo)
                db.add(models.Mark(student_id=student.id, subject_id=subj.id,
                                   exam_type=exam, score=round(pct * mx, 1), max_score=mx))

        total = 10
        db.add(models.BehaviorActivity(
            student_id=student.id,
            assignments_submitted=int(round(total * np.clip(np.random.normal(sub_rate, 0.1), 0, 1))),
            assignments_total=total,
            lms_logins_per_week=round(float(max(0, np.random.normal(lms, 1.5))), 1),
            extracurricular_count=int(np.random.choice([0, 1, 2, 3], p=[0.3, 0.35, 0.25, 0.1])),
        ))

    # --- FAQs for the chatbot
    faqs = [
        ("all", "What are the college timings?", "College runs from 9:00 AM to 4:30 PM, Monday to Friday."),
        ("all", "How is the progress score calculated?",
         "Progress score = 40% marks + 25% attendance + 20% assignments + 10% engagement + 5% improvement trend."),
        ("all", "How does the risk prediction work?",
         "A machine-learning model looks at attendance, marks, marks trend, assignments, LMS activity, failed subjects and previous GPA to classify students as Low, Medium or High risk."),
        ("student", "What is the minimum attendance required?", "You need at least 75% attendance to write exams."),
        ("parent", "How can I meet a faculty member?", "Book an appointment through the office between 2 PM and 4 PM."),
        ("parent", "How do I track my child's bus?", "Open the Bus Tracking page for the live map, or ask me 'When will the bus arrive?'."),
        ("faculty", "How do I view at-risk students?", "Open the Faculty Dashboard and check the At-Risk Students table."),
    ]
    for aud, q, a in faqs:
        db.add(models.FAQ(audience=aud, question=q, answer=a))

    db.commit()

    # Run the AI pipeline so dashboards have data straight away
    analytics = None
    try:
        from backend.services import analytics_service
        analytics = analytics_service.refresh_all(db)
    except RuntimeError as e:
        print("Skipped AI analysis:", e)

    print("Seed complete:")
    for model in [models.User, models.Faculty, models.Subject, models.Student, models.Attendance,
                  models.Mark, models.BehaviorActivity, models.Bus, models.RouteStop, models.FAQ]:
        print(f"  {model.__tablename__:20s} {db.query(model).count()}")
    if analytics:
        print(f"\nAI analysis: risk {analytics['risk_distribution']}, "
              f"avg progress {analytics['average_progress_score']}, "
              f"{analytics['alerts']['open_total']} open alerts")
    print("\nDemo logins:")
    print("  faculty1@eduassist.com / faculty123")
    print("  student1@eduassist.com / student123")
    print("  parent1@eduassist.com  / parent123")
    db.close()


if __name__ == "__main__":
    main()
