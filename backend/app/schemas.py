"""
Pydantic-Schemas: legen fest, welche Daten die API annimmt (…In)
und welche sie zurueckgibt (…Out). Falsche Eingaben -> automatisch 422.
"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app import models


# ---------------- Auth / Benutzer ----------------
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    username: str
    first_name: str
    last_name: str


class UserOut(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    role: str


class RegisterIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    password: str = Field(min_length=8, max_length=72)   # bcrypt nutzt max. 72 Bytes
    role: Literal["schueler", "lehrkraft"]               # admin kann man sich nicht selbst geben


# ---------------- Noten ----------------
class GradeIn(BaseModel):
    student_id: int
    class_subject_id: int
    category: Literal[models.GRADE_CATEGORIES]  # type: ignore[valid-type]
    value: float = Field(ge=4, le=10, description="Note 4-10")
    weight: float = Field(default=1.0, gt=0)
    date: Optional[date] = None
    homework_id: Optional[int] = None


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int
    class_subject_id: int
    category: str
    weight: float
    value: float
    date: date


# ---------------- Hausaufgaben ----------------
class HomeworkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    class_subject_id: int
    description: str
    due_date: datetime


class HomeworkConfirmIn(BaseModel):
    homework_id: int


# ---------------- Anwesenheit ----------------
class AttendanceIn(BaseModel):
    student_id: int
    lesson_id: int
    status: Literal[models.ATTENDANCE_STATUS]  # type: ignore[valid-type]


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int
    lesson_id: int
    status: str
    excuse_id: Optional[int] = None


# ---------------- Stundenplan ----------------
class TimetableOut(BaseModel):
    id: int
    class_subject_id: int
    subject: str
    class_name: str
    weekday: str
    start_time: str
    end_time: str
    room: Optional[str] = None


# ---------------- Quiz ----------------
class QuizSubmitIn(BaseModel):
    quiz_id: int
    score: int = Field(ge=0)


# ---------------- Klassen / SchuelerInnen ----------------
class ClassOut(BaseModel):
    id: int
    name: str
    school_year_id: int
    school_year: str


class StudentOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    username: str
    class_name: Optional[str] = None


class StudentIdIn(BaseModel):
    student_id: int


# ---------------- Faecher (= class_subjects) ----------------
class SubjectOut(BaseModel):
    id: int                      # class_subjects.id
    teacher_id: int
    subject_name: str
    class_name: str
    teacher_name: str
    file_count: int
    student_count: int


class SubjectCreateIn(BaseModel):
    class_id: int
    name: str = Field(min_length=1, max_length=150)


# ---------------- Materialien ----------------
class MaterialOut(BaseModel):
    id: int
    title: str
    original_name: str
    size_bytes: int
    uploaded_at: Optional[datetime]
    ext: str


class RecentMaterialOut(BaseModel):
    id: int
    title: str
    uploaded_at: Optional[datetime]
    subject_name: str
    ext: str


class UploadConfigOut(BaseModel):
    allowed_extensions: list[str]
    max_size_mb: int


# ---------------- allgemein ----------------
class StatusOut(BaseModel):
    status: str
    detail: Optional[dict] = None
