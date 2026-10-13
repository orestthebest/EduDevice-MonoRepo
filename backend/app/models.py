"""
EduDevice REST-API - Datenbankmodelle (ORM), Schema V4.3
Bildet die Tabellen aus Joriks Schema V4 ab, die von der API benutzt werden.
Die Tabellen werden NICHT von der API erzeugt - das macht das SQL-Schema.
"""

import enum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, Time, Boolean,
    DECIMAL, ForeignKey, Enum, TIMESTAMP, func, UniqueConstraint,
)
from app.core.database import Base


class RoleEnum(str, enum.Enum):
    schueler = "schueler"
    lehrkraft = "lehrkraft"
    admin = "admin"


GRADE_CATEGORIES = (
    "homework", "mini_test", "oral", "presentation", "classwork",
    "participation", "behaviour", "schularbeit", "project",
)
ATTENDANCE_STATUS = ("anwesend", "abwesend", "verspaetet")
WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr")


# ---------------- Benutzer ----------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    username = Column(String(50), nullable=False, unique=True)
    role = Column(Enum(RoleEnum), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


# ---------------- Schulstruktur ----------------
class SchoolYear(Base):
    __tablename__ = "school_years"
    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String(20), nullable=False, unique=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)


class SchoolClass(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    school_year_id = Column(Integer, ForeignKey("school_years.id"), nullable=False)
    name = Column(String(20), nullable=False)


class StudentClass(Base):
    __tablename__ = "student_classes"
    __table_args__ = (UniqueConstraint("student_id", "class_id", name="uq_student_class"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False, unique=True)


class ClassSubject(Base):
    """Welche Lehrkraft unterrichtet welches Fach in welcher Klasse."""
    __tablename__ = "class_subjects"
    __table_args__ = (UniqueConstraint("class_id", "subject_id", name="uq_class_subject"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)


class ClassSubjectStudent(Base):
    """V4.3: welche SchuelerInnen in einem Fach eingetragen sind (WebApp von Orest)."""
    __tablename__ = "class_subject_students"
    __table_args__ = (UniqueConstraint("class_subject_id", "student_id", name="uq_cs_student"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    class_subject_id = Column(Integer, ForeignKey("class_subjects.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    added_at = Column(DateTime, server_default=func.now())


class Material(Base):
    """V4.3: Lernmaterialien. Die Datei liegt im Upload-Ordner, hier nur die Metadaten."""
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, autoincrement=True)
    class_subject_id = Column(Integer, ForeignKey("class_subjects.id", ondelete="CASCADE"), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(150), nullable=False)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(100), nullable=False, unique=True)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, server_default=func.now())


# ---------------- Stundenplan / Anwesenheit ----------------
class TimetableEntry(Base):
    __tablename__ = "timetable"
    id = Column(Integer, primary_key=True, autoincrement=True)
    class_subject_id = Column(Integer, ForeignKey("class_subjects.id"), nullable=False)
    weekday = Column(Enum(*WEEKDAYS, name="weekday"), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    room = Column(String(50))


class Lesson(Base):
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timetable_id = Column(Integer, ForeignKey("timetable.id"), nullable=False)
    date = Column(Date, nullable=False)
    cancelled = Column(Boolean, nullable=False, default=False)


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    status = Column(Enum(*ATTENDANCE_STATUS, name="attendance_status"), nullable=False)
    excuse_id = Column(Integer, nullable=True)


# ---------------- Hausaufgaben ----------------
class Homework(Base):
    __tablename__ = "homework"
    id = Column(Integer, primary_key=True, autoincrement=True)
    class_subject_id = Column(Integer, ForeignKey("class_subjects.id"), nullable=False)
    description = Column(Text, nullable=False)
    due_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class HomeworkConfirmation(Base):
    __tablename__ = "homework_confirmations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    homework_id = Column(Integer, ForeignKey("homework.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    confirmed_at = Column(TIMESTAMP, nullable=True)
    status = Column(Enum("confirmed", "excused", name="confirmation_status"),
                    nullable=False, default="confirmed")


# ---------------- Noten ----------------
class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    class_subject_id = Column(Integer, ForeignKey("class_subjects.id"), nullable=False)
    category = Column(Enum(*GRADE_CATEGORIES, name="grade_category"), nullable=False)
    weight = Column(DECIMAL(4, 2), nullable=False, default=1.00)
    value = Column(DECIMAL(3, 1), nullable=False)
    date = Column(Date, nullable=False)
    homework_id = Column(Integer, ForeignKey("homework.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ---------------- Quiz ----------------
class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(150), nullable=False)
    class_subject_id = Column(Integer, ForeignKey("class_subjects.id"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class QuizResult(Base):
    __tablename__ = "quiz_results"
    __table_args__ = (UniqueConstraint("quiz_id", "student_id", name="uq_quiz_result"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Integer, nullable=False)
    submitted_at = Column(TIMESTAMP, server_default=func.now())
