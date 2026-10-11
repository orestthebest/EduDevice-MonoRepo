"""
Zugriffsregeln, die von mehreren Routern gebraucht werden.
Grundsatz: SchuelerIn sieht nur Eigenes, Lehrkraft nur eigene Faecher, Admin alles.
"""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models as m
from app.core.security import role_of
from app.schemas import StudentOut, SubjectOut


# ---------------- Klassen ----------------
def student_class_ids(db: Session, student_id: int) -> list[int]:
    return [r[0] for r in db.query(m.StudentClass.class_id).filter(m.StudentClass.student_id == student_id)]


def check_student_in_class(db: Session, student_id: int, class_id: int) -> None:
    if class_id not in student_class_ids(db, student_id):
        raise HTTPException(status_code=400, detail="SchuelerIn ist nicht in dieser Klasse")


# ---------------- class_subjects ----------------
def get_class_subject_or_404(db: Session, cs_id: int) -> m.ClassSubject:
    cs = db.get(m.ClassSubject, cs_id)
    if cs is None:
        raise HTTPException(status_code=404, detail="Fach nicht gefunden")
    return cs


def check_teaches(user: m.User, cs: m.ClassSubject) -> None:
    """Lehrkraft darf nur in eigenen Faechern schreiben; Admin darf alles."""
    if role_of(user) == "lehrkraft" and cs.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Sie unterrichten dieses Fach in dieser Klasse nicht")


def own_subject_or_403(db: Session, cs_id: int, user: m.User) -> m.ClassSubject:
    """Nur die Lehrkraft DIESES Fachs (fuer Upload, Schuelerliste, Loeschen)."""
    cs = get_class_subject_or_404(db, cs_id)
    if role_of(user) != "lehrkraft" or cs.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Nur die Lehrkraft dieses Fachs darf das")
    return cs


def filter_subjects_for_user(query, user: m.User):
    """schueler -> nur eingetragene Faecher, lehrkraft -> eigene, admin -> alle."""
    role = role_of(user)
    if role == "schueler":
        return query.join(m.ClassSubjectStudent,
                          (m.ClassSubjectStudent.class_subject_id == m.ClassSubject.id)
                          & (m.ClassSubjectStudent.student_id == user.id))
    if role == "lehrkraft":
        return query.filter(m.ClassSubject.teacher_id == user.id)
    return query


def subject_query(db: Session):
    """Fach mit Fachname, Klasse, Lehrkraft, Anzahl Dateien und Anzahl SchuelerInnen."""
    file_count = (select(func.count(m.Material.id))
                  .where(m.Material.class_subject_id == m.ClassSubject.id)
                  .correlate(m.ClassSubject).scalar_subquery())
    student_count = (select(func.count(m.ClassSubjectStudent.id))
                     .where(m.ClassSubjectStudent.class_subject_id == m.ClassSubject.id)
                     .correlate(m.ClassSubject).scalar_subquery())
    return (db.query(m.ClassSubject, m.Subject.name, m.SchoolClass.name,
                     m.User.first_name, m.User.last_name, file_count, student_count)
            .join(m.Subject, m.Subject.id == m.ClassSubject.subject_id)
            .join(m.SchoolClass, m.SchoolClass.id == m.ClassSubject.class_id)
            .join(m.User, m.User.id == m.ClassSubject.teacher_id))


def to_subject_out(row) -> SubjectOut:
    cs, subject_name, class_name, t_first, t_last, files, students = row
    return SubjectOut(id=cs.id, teacher_id=cs.teacher_id, subject_name=subject_name,
                      class_name=class_name, teacher_name=f"{t_first} {t_last}",
                      file_count=files or 0, student_count=students or 0)


def subject_for_user_or_404(db: Session, cs_id: int, user: m.User) -> SubjectOut:
    """Kein Zugriff -> 404 (wir verraten nicht, dass es das Fach gibt)."""
    row = filter_subjects_for_user(subject_query(db), user).filter(m.ClassSubject.id == cs_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Fach nicht gefunden")
    return to_subject_out(row)


def student_out(u: m.User, class_name: str | None = None) -> StudentOut:
    return StudentOut(id=u.id, first_name=u.first_name, last_name=u.last_name,
                      username=u.username, class_name=class_name)
