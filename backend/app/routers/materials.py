"""Lernmaterialien (ersetzt files.js + routes/(app)/materials/[id]/+server.js)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models as m
from app.core.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_MB
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.schemas import MaterialOut, RecentMaterialOut, UploadConfigOut
from app.services.access import filter_subjects_for_user, own_subject_or_403, subject_for_user_or_404
from app.services.files import delete_stored_file, ext_of, save_upload, stored_path

router = APIRouter(tags=["Materialien"])


def material_out(x: m.Material) -> MaterialOut:
    return MaterialOut(id=x.id, title=x.title, original_name=x.original_name, size_bytes=x.size_bytes,
                       uploaded_at=x.uploaded_at, ext=ext_of(x.original_name))


@router.get("/materials/config", response_model=UploadConfigOut)
def upload_config(current: m.User = Depends(get_current_user)):
    """Erlaubte Dateitypen und max. Groesse (fuer das Upload-Formular)."""
    return UploadConfigOut(allowed_extensions=sorted(ALLOWED_EXTENSIONS), max_size_mb=MAX_UPLOAD_MB)


@router.get("/materials/recent", response_model=list[RecentMaterialOut])
def recent_materials(limit: int = 6, db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    """Neueste Materialien aus den Faechern des Users (Dashboard)."""
    limit = max(1, min(limit, 50))
    query = (db.query(m.Material, m.Subject.name)
             .join(m.ClassSubject, m.ClassSubject.id == m.Material.class_subject_id)
             .join(m.Subject, m.Subject.id == m.ClassSubject.subject_id))
    rows = (filter_subjects_for_user(query, current)
            .order_by(m.Material.uploaded_at.desc(), m.Material.id.desc()).limit(limit).all())
    return [RecentMaterialOut(id=x.id, title=x.title, uploaded_at=x.uploaded_at,
                              subject_name=name, ext=ext_of(x.original_name)) for x, name in rows]


@router.get("/materials/{material_id}/download")
def download_material(material_id: int, db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    mat = db.get(m.Material, material_id)
    if mat is None:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")
    subject_for_user_or_404(db, mat.class_subject_id, current)   # Zugriff pruefen
    path = stored_path(mat.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Datei fehlt am Server")
    # attachment + Originalname (auch mit Umlauten)
    return FileResponse(path, media_type=mat.mime_type, filename=mat.original_name)


@router.get("/subjects/{cs_id}/materials", response_model=list[MaterialOut])
def list_materials(cs_id: int, db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    subject_for_user_or_404(db, cs_id, current)
    mats = (db.query(m.Material).filter(m.Material.class_subject_id == cs_id)
            .order_by(m.Material.uploaded_at.desc(), m.Material.id.desc()).all())
    return [material_out(x) for x in mats]


@router.post("/subjects/{cs_id}/materials", response_model=MaterialOut, status_code=201)
async def upload_material(cs_id: int, title: str = Form(...), file: UploadFile = File(...),
                          db: Session = Depends(get_db), current: m.User = Depends(require_roles("lehrkraft"))):
    own_subject_or_403(db, cs_id, current)
    title = title.strip()
    if not title or len(title) > 150:
        raise HTTPException(status_code=400, detail="Bitte einen Titel eingeben (max. 150 Zeichen)")
    original_name, stored_name, mime, size = await save_upload(file)
    try:
        mat = m.Material(class_subject_id=cs_id, uploaded_by=current.id, title=title,
                         original_name=original_name, stored_name=stored_name, mime_type=mime, size_bytes=size)
        db.add(mat)
        db.commit()
        db.refresh(mat)
    except Exception:
        # DB-Fehler -> Datei wieder loeschen, damit keine "Leichen" im Ordner bleiben
        db.rollback()
        delete_stored_file(stored_name)
        raise
    return material_out(mat)


@router.delete("/subjects/{cs_id}/materials/{material_id}")
def delete_material(cs_id: int, material_id: int, db: Session = Depends(get_db),
                    current: m.User = Depends(require_roles("lehrkraft"))):
    own_subject_or_403(db, cs_id, current)
    mat = db.query(m.Material).filter_by(id=material_id, class_subject_id=cs_id).first()
    if mat is None:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")
    stored = mat.stored_name
    db.delete(mat)
    db.commit()
    delete_stored_file(stored)
    return {"status": "geloescht", "id": material_id}
