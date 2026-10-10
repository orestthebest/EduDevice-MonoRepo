"""
EduDevice REST-API - Hauptanwendung (Ziel-M-4), angepasst an Schema V4.2
Endpunkte laut Ziel-Dokument:
  POST /auth/login                    (Username oder E-Mail + Passwort)
  GET  /grades/{student_id}            POST /grades           (nur Lehrkraft/Admin)
  GET  /homework/{subject_id}          POST /homework/confirm (nur SchuelerIn)
  GET  /attendance/{class_id}/{date}   POST /attendance       (nur Lehrkraft/Admin)
  GET  /timetable/{user_id}
  POST /quiz/submit                                           (nur SchuelerIn)
Alle Endpunkte ausser Login sind per JWT geschuetzt.
Rate-Limiting am Login: max. 10 Versuche pro Minute.
"""

import os
from datetime import date as date_type, datetime
from typing import Literal, Optional

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import models
from database import get_db
from auth import (
    verify_password, create_access_token, get_current_user, require_roles, role_of,
)

# ---------------------------------------------------------------------
# App, Rate-Limiter, CORS
# ---------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="EduDevice REST-API", version="2.2 (Schema V4.2)")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: erlaubt dem Frontend (Orest), die API aus dem Browser aufzurufen.
# Entwicklung: "*". Spaeter auf die echte Domain einschraenken.
_origins = os.getenv("EDUDEVICE_CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEEKDAY_ORDER = {d: i for i, d in enumerate(models.WEEKDAYS)}


# ---------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------
def student_class_ids(db: Session, student_id: int) -> list[int]:
    rows = db.query(models.StudentClass.class_id).filter(
        models.StudentClass.student_id == student_id).all()
    return [r[0] for r in rows]


def get_class_subject_or_404(db: Session, class_subject_id: int) -> models.ClassSubject:
    cs = db.get(models.ClassSubject, class_subject_id)
    if cs is None:
        raise HTTPException(status_code=404, detail="Klasse/Fach-Zuordnung nicht gefunden")
    return cs


def check_teaches(user: models.User, cs: models.ClassSubject) -> None:
    """Lehrkraefte duerfen nur in ihren eigenen Faechern schreiben; Admin darf alles."""
    if role_of(user) == "lehrkraft" and cs.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Sie unterrichten dieses Fach in dieser Klasse nicht")


def check_student_in_class(db: Session, student_id: int, class_id: int) -> None:
    if class_id not in student_class_ids(db, student_id):
        raise HTTPException(status_code=400, detail="SchuelerIn ist nicht in dieser Klasse")


# ---------------------------------------------------------------------
# Schemas (Ein-/Ausgabe)
# ---------------------------------------------------------------------
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    username: str
    first_name: str
    last_name: str


class GradeIn(BaseModel):
    student_id: int
    class_subject_id: int
    category: Literal[models.GRADE_CATEGORIES]  # type: ignore[valid-type]
    value: float = Field(ge=4, le=10, description="Note 4-10")
    weight: float = Field(default=1.0, gt=0)
    date: Optional[date_type] = None
    homework_id: Optional[int] = None


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int
    class_subject_id: int
    category: str
    weight: float
    value: float
    date: date_type


class HomeworkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    class_subject_id: int
    description: str
    due_date: datetime


class HomeworkConfirmIn(BaseModel):
    homework_id: int


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


class TimetableOut(BaseModel):
    id: int
    class_subject_id: int
    subject: str
    class_name: str
    weekday: str
    start_time: str
    end_time: str
    room: Optional[str] = None


class QuizSubmitIn(BaseModel):
    quiz_id: int
    score: int = Field(ge=0)


# ---------------------------------------------------------------------
# POST /auth/login  (Rate-Limit 10/Minute)
# ---------------------------------------------------------------------
@app.post("/auth/login", response_model=TokenOut, tags=["Auth"])
@limiter.limit("10/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    # Login mit Username (laut Ziel-M-4) oder alternativ mit E-Mail
    login_name = form.username.strip()
    user = db.query(models.User).filter(
        or_(models.User.username == login_name, models.User.email == login_name)
    ).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Falscher Username oder falsches Passwort")
    return TokenOut(
        access_token=create_access_token(user), role=role_of(user), user_id=user.id,
        username=user.username, first_name=user.first_name, last_name=user.last_name,
    )


# ---------------------------------------------------------------------
# Noten
# ---------------------------------------------------------------------
@app.get("/grades/{student_id}", response_model=list[GradeOut], tags=["Noten"])
def get_grades(student_id: int, db: Session = Depends(get_db),
               current: models.User = Depends(get_current_user)):
    role = role_of(current)
    query = db.query(models.Grade).filter(models.Grade.student_id == student_id)
    if role == "schueler":
        if current.id != student_id:
            raise HTTPException(status_code=403, detail="Nur eigene Noten einsehbar")
    elif role == "lehrkraft":
        # Lehrkraft sieht nur Noten aus ihren eigenen Faechern
        query = query.join(models.ClassSubject,
                           models.Grade.class_subject_id == models.ClassSubject.id
                           ).filter(models.ClassSubject.teacher_id == current.id)
    return query.order_by(models.Grade.date).all()


@app.post("/grades", response_model=GradeOut, status_code=201, tags=["Noten"])
def add_grade(grade: GradeIn, db: Session = Depends(get_db),
              current: models.User = Depends(require_roles("lehrkraft", "admin"))):
    cs = get_class_subject_or_404(db, grade.class_subject_id)
    check_teaches(current, cs)
    check_student_in_class(db, grade.student_id, cs.class_id)

    new_grade = models.Grade(
        student_id=grade.student_id,
        class_subject_id=grade.class_subject_id,
        category=grade.category,
        value=grade.value,
        weight=grade.weight,
        date=grade.date or date_type.today(),
        homework_id=grade.homework_id,
    )
    db.add(new_grade)
    db.commit()
    db.refresh(new_grade)
    return new_grade


# ---------------------------------------------------------------------
# Hausaufgaben
# ---------------------------------------------------------------------
@app.get("/homework/{subject_id}", response_model=list[HomeworkOut], tags=["Hausaufgaben"])
def get_homework(subject_id: int, db: Session = Depends(get_db),
                 current: models.User = Depends(get_current_user)):
    query = db.query(models.Homework).join(
        models.ClassSubject, models.Homework.class_subject_id == models.ClassSubject.id
    ).filter(models.ClassSubject.subject_id == subject_id)

    role = role_of(current)
    if role == "schueler":
        query = query.filter(models.ClassSubject.class_id.in_(student_class_ids(db, current.id)))
    elif role == "lehrkraft":
        query = query.filter(models.ClassSubject.teacher_id == current.id)
    return query.order_by(models.Homework.due_date).all()


@app.post("/homework/confirm", tags=["Hausaufgaben"])
def confirm_homework(data: HomeworkConfirmIn, db: Session = Depends(get_db),
                     current: models.User = Depends(require_roles("schueler"))):
    hw = db.get(models.Homework, data.homework_id)
    if hw is None:
        raise HTTPException(status_code=404, detail="Hausaufgabe nicht gefunden")
    cs = get_class_subject_or_404(db, hw.class_subject_id)
    if cs.class_id not in student_class_ids(db, current.id):
        raise HTTPException(status_code=403, detail="Diese Hausaufgabe gehoert nicht zu Ihrer Klasse")

    conf = db.query(models.HomeworkConfirmation).filter_by(
        homework_id=data.homework_id, student_id=current.id).first()
    if conf is None:
        conf = models.HomeworkConfirmation(homework_id=data.homework_id, student_id=current.id)
        db.add(conf)
    conf.confirmed_at = datetime.now()
    conf.status = "confirmed"
    db.commit()
    return {"status": "bestaetigt", "homework_id": data.homework_id}


# ---------------------------------------------------------------------
# Anwesenheit
# ---------------------------------------------------------------------
@app.get("/attendance/{class_id}/{date}", response_model=list[AttendanceOut], tags=["Anwesenheit"])
def get_attendance(class_id: int, date: date_type, db: Session = Depends(get_db),
                   current: models.User = Depends(require_roles("lehrkraft", "admin"))):
    query = (db.query(models.Attendance)
             .join(models.Lesson, models.Attendance.lesson_id == models.Lesson.id)
             .join(models.TimetableEntry, models.Lesson.timetable_id == models.TimetableEntry.id)
             .join(models.ClassSubject, models.TimetableEntry.class_subject_id == models.ClassSubject.id)
             .filter(models.ClassSubject.class_id == class_id, models.Lesson.date == date))
    if role_of(current) == "lehrkraft":
        query = query.filter(models.ClassSubject.teacher_id == current.id)
    return query.all()


@app.post("/attendance", response_model=AttendanceOut, tags=["Anwesenheit"])
def add_attendance(entry: AttendanceIn, db: Session = Depends(get_db),
                   current: models.User = Depends(require_roles("lehrkraft", "admin"))):
    lesson = db.get(models.Lesson, entry.lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Unterrichtsstunde nicht gefunden")
    tt = db.get(models.TimetableEntry, lesson.timetable_id)
    cs = get_class_subject_or_404(db, tt.class_subject_id)
    check_teaches(current, cs)
    check_student_in_class(db, entry.student_id, cs.class_id)

    # Pro SchuelerIn und Stunde gibt es genau einen Eintrag -> aktualisieren statt doppelt anlegen
    record = db.query(models.Attendance).filter_by(
        student_id=entry.student_id, lesson_id=entry.lesson_id).first()
    if record is None:
        record = models.Attendance(student_id=entry.student_id, lesson_id=entry.lesson_id)
        db.add(record)
    record.status = entry.status
    db.commit()
    db.refresh(record)
    return record


# ---------------------------------------------------------------------
# Stundenplan
# ---------------------------------------------------------------------
@app.get("/timetable/{user_id}", response_model=list[TimetableOut], tags=["Stundenplan"])
def get_timetable(user_id: int, db: Session = Depends(get_db),
                  current: models.User = Depends(get_current_user)):
    if role_of(current) != "admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="Nur eigener Stundenplan einsehbar")
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    query = (db.query(models.TimetableEntry, models.Subject.name, models.SchoolClass.name)
             .join(models.ClassSubject, models.TimetableEntry.class_subject_id == models.ClassSubject.id)
             .join(models.Subject, models.ClassSubject.subject_id == models.Subject.id)
             .join(models.SchoolClass, models.ClassSubject.class_id == models.SchoolClass.id))

    target_role = role_of(target)
    if target_role == "schueler":
        query = query.filter(models.ClassSubject.class_id.in_(student_class_ids(db, user_id)))
    elif target_role == "lehrkraft":
        query = query.filter(models.ClassSubject.teacher_id == user_id)
    else:
        return []

    rows = query.all()
    rows.sort(key=lambda r: (WEEKDAY_ORDER.get(r[0].weekday, 9), r[0].start_time))
    return [
        TimetableOut(
            id=t.id, class_subject_id=t.class_subject_id, subject=subject_name,
            class_name=class_name, weekday=t.weekday,
            start_time=t.start_time.strftime("%H:%M"), end_time=t.end_time.strftime("%H:%M"),
            room=t.room,
        )
        for t, subject_name, class_name in rows
    ]


# ---------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------
@app.post("/quiz/submit", status_code=201, tags=["Quiz"])
def submit_quiz(data: QuizSubmitIn, db: Session = Depends(get_db),
                current: models.User = Depends(require_roles("schueler"))):
    quiz = db.get(models.Quiz, data.quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz nicht gefunden")
    cs = get_class_subject_or_404(db, quiz.class_subject_id)
    if cs.class_id not in student_class_ids(db, current.id):
        raise HTTPException(status_code=403, detail="Dieses Quiz gehoert nicht zu Ihrer Klasse")
    # Pro SchuelerIn nur eine Abgabe pro Quiz (UNIQUE in der Datenbank)
    if db.query(models.QuizResult).filter_by(quiz_id=data.quiz_id, student_id=current.id).first():
        raise HTTPException(status_code=409, detail="Dieses Quiz wurde bereits abgegeben")
    result = models.QuizResult(quiz_id=data.quiz_id, student_id=current.id, score=data.score)
    db.add(result)
    db.commit()
    return {"status": "gespeichert", "quiz_id": data.quiz_id, "score": data.score}


@app.get("/", tags=["Info"])
def root():
    return {"message": "EduDevice REST-API laeuft. Doku unter /docs"}
