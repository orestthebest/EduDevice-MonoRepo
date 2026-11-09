"""Entschuldigungssystem (O-3, Schema V4.6).
SchuelerIn entschuldigt eigene Fehlstunden, der Klassenvorstand (classes.class_teacher_id)
nimmt an oder lehnt ab. Welche Fehlstunden zu einer Entschuldigung gehoeren, steht in
attendance.excuse_id (keine Extra-Tabelle).

"Unentschuldigt" = attendance.status abwesend/verspaetet UND (keine Entschuldigung ODER abgelehnt).
Abgelehnte Fehlstunden koennen neu eingereicht werden (excuse_id wird ueberschrieben)."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, aliased

from app import models as m
from app.core.config import EXCUSE_DIR, EXCUSE_MAX_BYTES, EXCUSE_MAX_FILES
from app.core.database import get_db
from app.core.security import get_current_user, require_roles, role_of
from app.schemas import AbsenceOut, ExcuseAttachmentOut, ExcuseIn, ExcuseOut, ExcuseReviewIn

router = APIRouter(tags=["Entschuldigungen"])


# ---------------- Hilfsfunktionen ----------------
def absence_query(db: Session):
    """Fehlstunde mit Datum, Uhrzeit, Fach und Status der Entschuldigung."""
    return (db.query(m.Attendance, m.Lesson.date, m.TimetableEntry.start_time, m.TimetableEntry.end_time,
                     m.Subject.name, m.Excuse.status)
            .join(m.Lesson, m.Lesson.id == m.Attendance.lesson_id)
            .join(m.TimetableEntry, m.TimetableEntry.id == m.Lesson.timetable_id)
            .join(m.ClassSubject, m.ClassSubject.id == m.TimetableEntry.class_subject_id)
            .join(m.Subject, m.Subject.id == m.ClassSubject.subject_id)
            .outerjoin(m.Excuse, m.Excuse.id == m.Attendance.excuse_id))


def unexcused_filter(query, student_id: int):
    return query.filter(m.Attendance.student_id == student_id,
                        m.Attendance.status.in_(m.ABSENCE_STATUS),
                        m.Lesson.cancelled.is_(False),
                        or_(m.Attendance.excuse_id.is_(None), m.Excuse.status == "rejected"))


def to_absence_out(row) -> AbsenceOut:
    att, day, start, end, subject, excuse_status = row
    return AbsenceOut(attendance_id=att.id, date=day, start_time=start, end_time=end, subject_name=subject,
                      status=att.status, excuse_id=att.excuse_id, excuse_status=excuse_status)


def excuse_out(db: Session, exc: m.Excuse, class_name: Optional[str] = None) -> ExcuseOut:
    rows = (absence_query(db).filter(m.Attendance.excuse_id == exc.id)
            .order_by(m.Lesson.date, m.TimetableEntry.start_time).all())
    student = db.get(m.User, exc.student_id)
    reviewer = db.get(m.User, exc.reviewed_by) if exc.reviewed_by else None
    return ExcuseOut(id=exc.id, student_id=exc.student_id,
                     student_name=f"{student.first_name} {student.last_name}", class_name=class_name,
                     date_from=exc.date_from, date_to=exc.date_to, reason=exc.reason, status=exc.status,
                     teacher_comment=exc.teacher_comment, reviewed_by=exc.reviewed_by,
                     reviewed_by_name=f"{reviewer.first_name} {reviewer.last_name}" if reviewer else None,
                     reviewed_at=exc.reviewed_at, submitted_at=exc.submitted_at,
                     absences=[to_absence_out(r) for r in rows],
                     attachments=[ExcuseAttachmentOut(id=a.id, original_name=a.original_name,
                                                      size_bytes=a.size_bytes)
                                  for a in db.query(m.ExcuseAttachment).filter_by(excuse_id=exc.id)
                                  .order_by(m.ExcuseAttachment.id)])


def class_teacher_class_name(db: Session, student_id: int, teacher: m.User) -> Optional[str]:
    """Name der Klasse, in der `teacher` Klassenvorstand von `student_id` ist (Admin: irgendeine Klasse).
    None = kein Klassenvorstand dieser SchuelerIn."""
    q = (db.query(m.SchoolClass.name)
         .join(m.StudentClass, m.StudentClass.class_id == m.SchoolClass.id)
         .filter(m.StudentClass.student_id == student_id))
    if role_of(teacher) != "admin":
        q = q.filter(m.SchoolClass.class_teacher_id == teacher.id)
    row = q.order_by(m.SchoolClass.id.desc()).first()
    return row[0] if row else None


# ---------------- SchuelerIn ----------------
@router.get("/attendance/me", response_model=list[AbsenceOut])
def my_absences(unexcused: bool = False, db: Session = Depends(get_db),
                current: m.User = Depends(require_roles("schueler"))):
    """Eigene Fehlstunden (abwesend/verspaetet). unexcused=true -> nur die, die man noch entschuldigen kann."""
    q = absence_query(db)
    if unexcused:
        q = unexcused_filter(q, current.id)
    else:
        q = q.filter(m.Attendance.student_id == current.id, m.Attendance.status.in_(m.ABSENCE_STATUS))
    rows = q.order_by(m.Lesson.date.desc(), m.TimetableEntry.start_time).all()
    return [to_absence_out(r) for r in rows]


@router.post("/excuses", response_model=ExcuseOut, status_code=201)
def create_excuse(data: ExcuseIn, db: Session = Depends(get_db),
                  current: m.User = Depends(require_roles("schueler"))):
    """Entschuldigung fuer eigene, noch unentschuldigte Fehlstunden einreichen."""
    ids = set(data.attendance_ids)
    rows = (unexcused_filter(absence_query(db), current.id)
            .filter(m.Attendance.id.in_(ids))
            .with_for_update().all())                         # gleichzeitiges Einreichen verhindern
    if len(rows) != len(ids):
        raise HTTPException(status_code=400,
                            detail="Mindestens eine Fehlstunde gehoert nicht dir oder ist schon entschuldigt")
    reason = data.reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Bitte einen Grund angeben")

    days = [r[1] for r in rows]
    exc = m.Excuse(student_id=current.id, date_from=min(days), date_to=max(days),
                   reason=reason, status="pending")
    db.add(exc)
    db.flush()                                                   # exc.id wird vergeben
    for r in rows:
        r[0].excuse_id = exc.id                                  # abgelehnte werden ueberschrieben
    db.commit()
    db.refresh(exc)
    return excuse_out(db, exc)


@router.get("/excuses/me", response_model=list[ExcuseOut])
def my_excuses(db: Session = Depends(get_db), current: m.User = Depends(require_roles("schueler"))):
    excuses = (db.query(m.Excuse).filter(m.Excuse.student_id == current.id)
               .order_by(m.Excuse.submitted_at.desc(), m.Excuse.id.desc()).all())
    return [excuse_out(db, e) for e in excuses]


# ---------------- Klassenvorstand ----------------
@router.get("/excuses/class-teacher", response_model=list[ExcuseOut])
def class_teacher_excuses(status: Optional[Literal["pending", "accepted", "rejected"]] = None,
                          db: Session = Depends(get_db),
                          current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    """Entschuldigungen der SchuelerInnen aus Klassen, in denen ich Klassenvorstand bin (Admin: alle)."""
    sc = aliased(m.SchoolClass)
    q = (db.query(m.Excuse, sc.name)
         .join(m.StudentClass, m.StudentClass.student_id == m.Excuse.student_id)
         .join(sc, sc.id == m.StudentClass.class_id))
    if role_of(current) != "admin":
        q = q.filter(sc.class_teacher_id == current.id)
    if status:
        q = q.filter(m.Excuse.status == status)
    seen, result = set(), []
    for exc, class_name in q.order_by(m.Excuse.submitted_at.desc(), m.Excuse.id.desc()).all():
        if exc.id not in seen:                                   # SchuelerIn in mehreren Klassen -> nur einmal
            seen.add(exc.id)
            result.append(excuse_out(db, exc, class_name))
    return result


@router.patch("/excuses/{excuse_id}", response_model=ExcuseOut)
def review_excuse(excuse_id: int, data: ExcuseReviewIn, db: Session = Depends(get_db),
                  current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    """Annehmen oder ablehnen. Nur der Klassenvorstand der SchuelerIn (oder Admin), nur wenn noch offen."""
    exc = db.get(m.Excuse, excuse_id)
    class_name = class_teacher_class_name(db, exc.student_id, current) if exc else None
    if exc is None or class_name is None:
        raise HTTPException(status_code=404, detail="Entschuldigung nicht gefunden")
    if exc.status != "pending":
        raise HTTPException(status_code=409, detail="Diese Entschuldigung wurde schon bearbeitet")
    comment = (data.teacher_comment or "").strip()
    exc.status = data.status
    exc.teacher_comment = comment or None
    exc.reviewed_by = current.id
    exc.reviewed_at = datetime.now().replace(microsecond=0)
    db.commit()
    db.refresh(exc)
    return excuse_out(db, exc, class_name)


# ---------------- Anhaenge (V4.9) ----------------
# Oft Arztbestaetigungen = Gesundheitsdaten. Deshalb: eigener Ordner, Typ wird am INHALT geprueft,
# sehen duerfen nur die SchuelerIn selbst, ihr Klassenvorstand und der Admin.
ATTACHMENT_TYPES = {                 # Endung -> (MIME-Typ, Anfang der Datei)
    "pdf": ("application/pdf", (b"%PDF-",)),
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
}


def attachment_path(stored_name: str) -> Path:
    return EXCUSE_DIR / Path(stored_name).name          # .name: kein "../"


def own_pending_excuse(db: Session, excuse_id: int, student: m.User) -> m.Excuse:
    exc = db.get(m.Excuse, excuse_id)
    if exc is None or exc.student_id != student.id:
        raise HTTPException(status_code=404, detail="Entschuldigung nicht gefunden")
    if exc.status != "pending":
        raise HTTPException(status_code=409, detail="Die Entschuldigung wurde schon bearbeitet")
    return exc


@router.post("/excuses/{excuse_id}/attachments", response_model=ExcuseAttachmentOut, status_code=201)
def upload_attachment(excuse_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                      current: m.User = Depends(require_roles("schueler"))):
    """Anhang hochladen: PDF/JPG/PNG, max. 5 MB, max. 3 pro Entschuldigung, nur solange offen."""
    exc = own_pending_excuse(db, excuse_id, current)
    if db.query(m.ExcuseAttachment).filter_by(excuse_id=exc.id).count() >= EXCUSE_MAX_FILES:
        raise HTTPException(status_code=409, detail=f"Hoechstens {EXCUSE_MAX_FILES} Anhaenge pro Entschuldigung")

    original = Path(file.filename or "").name.strip()[:255] or "anhang"
    ext = Path(original).suffix.lstrip(".").lower()
    if ext not in ATTACHMENT_TYPES:
        raise HTTPException(status_code=400, detail="Nur PDF, JPG oder PNG erlaubt")
    data = file.file.read(EXCUSE_MAX_BYTES + 1)          # nie mehr als 5 MB + 1 Byte in den Speicher
    if len(data) > EXCUSE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist zu gross (max. 5 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswaehlen")
    mime, magic = ATTACHMENT_TYPES[ext]
    if not data.startswith(magic):                        # z. B. umbenannte .exe oder .html
        raise HTTPException(status_code=400, detail="Der Inhalt passt nicht zur Dateiendung")

    stored = f"{uuid.uuid4()}.{'jpg' if ext == 'jpeg' else ext}"
    EXCUSE_DIR.mkdir(parents=True, exist_ok=True)
    attachment_path(stored).write_bytes(data)
    att = m.ExcuseAttachment(excuse_id=exc.id, original_name=original, stored_name=stored,
                             mime_type=mime, size_bytes=len(data))
    db.add(att)
    try:
        db.commit()
    except Exception:
        db.rollback()
        attachment_path(stored).unlink(missing_ok=True)
        raise
    db.refresh(att)
    return ExcuseAttachmentOut(id=att.id, original_name=att.original_name, size_bytes=att.size_bytes)


@router.get("/excuses/{excuse_id}/attachments/{att_id}/download")
def download_attachment(excuse_id: int, att_id: int, db: Session = Depends(get_db),
                        current: m.User = Depends(get_current_user)):
    """Nur die SchuelerIn selbst, ihr Klassenvorstand und der Admin. Alle anderen -> 404."""
    exc = db.get(m.Excuse, excuse_id)
    att = db.get(m.ExcuseAttachment, att_id)
    if exc is None or att is None or att.excuse_id != exc.id:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
    role = role_of(current)
    allowed = (exc.student_id == current.id or role == "admin"
               or (role == "lehrkraft" and class_teacher_class_name(db, exc.student_id, current)))
    if not allowed:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
    path = attachment_path(att.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Datei fehlt am Server")
    return FileResponse(path, media_type=att.mime_type, filename=att.original_name,
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@router.delete("/excuses/{excuse_id}/attachments/{att_id}", status_code=204)
def delete_attachment(excuse_id: int, att_id: int, db: Session = Depends(get_db),
                      current: m.User = Depends(require_roles("schueler"))):
    """Falschen Anhang wieder entfernen - nur die SchuelerIn selbst und nur solange offen."""
    exc = own_pending_excuse(db, excuse_id, current)
    att = db.get(m.ExcuseAttachment, att_id)
    if att is None or att.excuse_id != exc.id:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
    stored = att.stored_name
    db.delete(att)
    db.commit()
    attachment_path(stored).unlink(missing_ok=True)
    return Response(status_code=204)
