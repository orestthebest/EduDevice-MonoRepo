"""Quiz (Ziel-M-4): POST /quiz/submit  -  alt, nur fuer Quizzes ohne Fragen.
Neues Quiz-System mit Bewertung in der API: routers/quizzes.py"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models as m
from app.core.database import get_db
from app.core.security import require_roles
from app.schemas import QuizSubmitIn
from app.services.access import get_class_subject_or_404, student_class_ids

router = APIRouter(prefix="/quiz", tags=["Quiz"])


@router.post("/submit", status_code=201)
def submit_quiz(data: QuizSubmitIn, db: Session = Depends(get_db),
                current: m.User = Depends(require_roles("schueler"))):
    quiz = db.get(m.Quiz, data.quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz nicht gefunden")
    # Quizzes mit Fragen werden von der API bewertet (POST /quizzes/{id}/submit).
    # Hier wuerde sonst der Client den Score selbst bestimmen.
    if db.query(m.QuizQuestion).filter(m.QuizQuestion.quiz_id == quiz.id).first():
        raise HTTPException(status_code=409,
                            detail="Dieses Quiz hat Fragen - bitte POST /quizzes/{id}/submit verwenden")
    cs = get_class_subject_or_404(db, quiz.class_subject_id)
    if cs.class_id not in student_class_ids(db, current.id):
        raise HTTPException(status_code=403, detail="Dieses Quiz gehoert nicht zu Ihrer Klasse")
    # pro SchuelerIn nur eine Abgabe pro Quiz (UNIQUE in der DB)
    if db.query(m.QuizResult).filter_by(quiz_id=quiz.id, student_id=current.id).first():
        raise HTTPException(status_code=409, detail="Dieses Quiz wurde bereits abgegeben")
    db.add(m.QuizResult(quiz_id=quiz.id, student_id=current.id, score=data.score))
    db.commit()
    return {"status": "gespeichert", "quiz_id": quiz.id, "score": data.score}
