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
    profile_image: str | None = None   # V4.5, Bild unter GET /users/avatar/{profile_image}


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str = Field(min_length=8, max_length=72)   # bcrypt nutzt max. 72 Bytes
    role: Literal["schueler", "lehrkraft"]               # admin kann man sich nicht selbst geben


class ProfileUpdateIn(BaseModel):
    """PATCH /users/me: nur die E-Mail darf geaendert werden."""
    # andere Felder im Body (z. B. "role") werden ignoriert, nie uebernommen
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)


class AvatarOut(BaseModel):
    profile_image: str


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


# =====================================================================
# Quiz (V4.4) - Formate wie in docs/QUIZ_API.md
# =====================================================================
class QuizCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: Optional[str] = None


class QuizUpdateIn(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = None
    is_published: Optional[bool] = None


class OptionIn(BaseModel):
    option_text: str = Field(min_length=1, max_length=500)
    is_correct: bool = False


class QuestionIn(BaseModel):
    """mc: options · tf: correct · gap: gaps (akzeptierte Antworten pro {{n}})"""
    type: Literal["mc", "tf", "gap"]
    question_text: str = Field(min_length=1, max_length=5000)
    points: int = Field(default=1, ge=1, le=100)
    options: Optional[list[OptionIn]] = None
    correct: Optional[bool] = None
    gaps: Optional[list[list[str]]] = None


class OptionTeacherOut(BaseModel):
    id: int
    option_text: str
    is_correct: bool
    gap_index: Optional[int]
    position: int


class QuestionTeacherOut(BaseModel):
    id: int
    position: int
    type: str
    points: int
    question_text: str
    options: list[OptionTeacherOut]


class QuizTeacherOut(BaseModel):
    id: int
    class_subject_id: int
    title: str
    description: Optional[str]
    is_published: bool
    locked: bool
    max_score: int
    questions: list[QuestionTeacherOut]


class QuizListTeacherOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    is_published: bool
    locked: bool
    question_count: int
    max_score: int
    attempt_count: int
    created_at: Optional[datetime]


class MyResultShortOut(BaseModel):
    score: int
    max_score: int
    submitted_at: Optional[datetime]


class QuizListStudentOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    question_count: int
    max_score: int
    my_result: Optional[MyResultShortOut]


class OptionStudentOut(BaseModel):
    id: int
    option_text: str


class QuestionStudentOut(BaseModel):
    id: int
    position: int
    type: str
    points: int
    question_text: str
    options: Optional[list[OptionStudentOut]] = None
    gap_count: Optional[int] = None


class QuizTakeOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    max_score: int
    questions: list[QuestionStudentOut]


class AnswerIn(BaseModel):
    question_id: int
    option_ids: Optional[list[int]] = None
    gaps: Optional[list[str]] = None


class QuizSubmitAnswersIn(BaseModel):
    answers: list[AnswerIn] = Field(default_factory=list)


class QuestionResultOut(BaseModel):
    question_id: int
    question_text: str
    correct: bool
    points_awarded: int


class QuizResultOut(BaseModel):
    score: int
    max_score: int
    submitted_at: Optional[datetime]
    questions: list[QuestionResultOut]


class AttemptOut(BaseModel):
    student_id: int
    first_name: str
    last_name: str
    username: str
    score: int
    max_score: Optional[int]
    submitted_at: Optional[datetime]
