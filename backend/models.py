from datetime import datetime

from sqlalchemy import (
    JSON, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # student | parent | faculty


class Faculty(Base):
    __tablename__ = "faculty"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    department = Column(String)
    user = relationship("User")


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True)
    faculty_id = Column(Integer, ForeignKey("faculty.id"))


class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    stops = relationship("RouteStop", order_by="RouteStop.stop_order")


class RouteStop(Base):
    __tablename__ = "route_stops"
    id = Column(Integer, primary_key=True)
    route_id = Column(Integer, ForeignKey("routes.id"))
    stop_name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    stop_order = Column(Integer, nullable=False)


class Bus(Base):
    __tablename__ = "buses"
    id = Column(Integer, primary_key=True)
    bus_no = Column(String, unique=True, nullable=False)
    driver_name = Column(String)
    driver_phone = Column(String)
    capacity = Column(Integer)
    route_id = Column(Integer, ForeignKey("routes.id"))
    route = relationship("Route")


class BusLocation(Base):
    __tablename__ = "bus_locations"
    id = Column(Integer, primary_key=True)
    bus_id = Column(Integer, ForeignKey("buses.id"))
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    speed = Column(Float, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    parent_user_id = Column(Integer, ForeignKey("users.id"))
    roll_no = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    department = Column(String)
    year = Column(Integer)
    section = Column(String)
    prev_gpa = Column(Float)
    bus_id = Column(Integer, ForeignKey("buses.id"), nullable=True)


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    date = Column(Date, nullable=False)
    status = Column(String, nullable=False)  # present | absent


class Mark(Base):
    __tablename__ = "marks"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    exam_type = Column(String, nullable=False)  # internal1 | internal2 | model | assignment
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)


class BehaviorActivity(Base):
    __tablename__ = "behavior_activity"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), unique=True)
    assignments_submitted = Column(Integer)
    assignments_total = Column(Integer)
    lms_logins_per_week = Column(Float)
    extracurricular_count = Column(Integer)


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True)
    risk_level = Column(String)  # Low | Medium | High
    probability = Column(Float)
    top_factors = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True)
    type = Column(String)
    severity = Column(String)  # Info | Warning | Critical
    message = Column(Text)
    status = Column(String, default="open")  # open | resolved
    created_at = Column(DateTime, default=datetime.utcnow)


class ProgressScore(Base):
    __tablename__ = "progress_scores"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True)
    score = Column(Float)
    grade = Column(String)
    breakdown = Column(JSON)
    computed_at = Column(DateTime, default=datetime.utcnow)


class ChatLog(Base):
    __tablename__ = "chat_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String)
    question = Column(Text)
    answer = Column(Text)
    intent = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


class FAQ(Base):
    __tablename__ = "faqs"
    id = Column(Integer, primary_key=True)
    audience = Column(String)  # student | parent | faculty | all
    question = Column(Text)
    answer = Column(Text)
