"""
Quiz-System (V4.4) - Vertrag: docs/QUIZ_API.md

Regeln:
  * Die richtigen Antworten verlassen nie den Server fuer SchuelerInnen.
  * Die API bewertet. Jede Frage zaehlt ganz oder gar nicht.
  * Sobald es eine Abgabe gibt, ist das Quiz gesperrt (nur is_published darf sich noch aendern).
  * Kein Zugriff -> 404 (wir verraten nicht, dass es das Quiz gibt).
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m
from app.core.database import get_db
from app.core.security import get_current_user, require_roles, role_of
from app.schemas import (AttemptOut, MyResultShortOut, OptionStudentOut, OptionTeacherOut,
                         QuestionIn, QuestionResultOut, QuestionStudentOut, QuestionTeacherOut,
                         QuizCreateIn, QuizListStudentOut, QuizListTeacherOut, QuizResultOut,
                         QuizSubmitAnswersIn, QuizTakeOut, QuizTeacherOut, QuizUpdateIn)
from app.services.access import get_class_subject_or_404

router = APIRouter(tags=["Quiz"])

GAP_PATTERN = re.compile(r"\{\{(\d+)\}\}")
NOT_FOUND = "Quiz nicht gefunden"


# =====================================================================
# Hilfsfunktionen: Zugriff
# =====================================================================
def is_teacher_of(user: m.User, cs: m.ClassSubject) -> bool:
    return role_of(user) == "admin" or (role_of(user) == "lehrkraft" and cs.teacher_id == user.id)


def is_enrolled(db: Session, student_id: int, cs_id: int) -> bool:
    return db.query(m.ClassSubjectStudent).filter_by(class_subject_id=cs_id, student_id=student_id).first() is not None


def teacher_cs_or_404(db: Session, cs_id: int, user: m.User) -> m.ClassSubject:
    cs = db.get(m.ClassSubject, cs_id)
    if cs is None or not is_teacher_of(user, cs):
        raise HTTPException(status_code=404, detail="Fach nicht gefunden")
    return cs


def teacher_quiz_or_404(db: Session, quiz_id: int, user: m.User) -> m.Quiz:
    """Quiz, das die Lehrkraft (oder Admin) verwalten darf."""
    quiz = db.get(m.Quiz, quiz_id)
    if quiz is None or not is_teacher_of(user, get_class_subject_or_404(db, quiz.class_subject_id)):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return quiz


def student_quiz_or_404(db: Session, quiz_id: int, user: m.User, allow_unpublished_with_result=False) -> m.Quiz:
    """Quiz, das die SchuelerIn sehen darf: im Fach eingetragen + veroeffentlicht
    (oder - beim eigenen Ergebnis - schon abgegeben)."""
    quiz = db.get(m.Quiz, quiz_id)
    if quiz is None or not is_enrolled(db, user.id, quiz.class_subject_id):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if not quiz.is_published:
        if not (allow_unpublished_with_result and get_result(db, quiz.id, user.id)):
            raise HTTPException(status_code=404, detail=NOT_FOUND)
    return quiz


# =====================================================================
# Hilfsfunktionen: Daten
# =====================================================================
def get_questions(db: Session, quiz_id: int) -> list[m.QuizQuestion]:
    return (db.query(m.QuizQuestion).filter(m.QuizQuestion.quiz_id == quiz_id)
            .order_by(m.QuizQuestion.position, m.QuizQuestion.id).all())


def get_options(db: Session, question_id: int) -> list[m.QuizOption]:
    return (db.query(m.QuizOption).filter(m.QuizOption.question_id == question_id)
            .order_by(m.QuizOption.position, m.QuizOption.id).all())


def get_result(db: Session, quiz_id: int, student_id: int):
    return db.query(m.QuizResult).filter_by(quiz_id=quiz_id, student_id=student_id).first()


def attempt_count(db: Session, quiz_id: int) -> int:
    return db.query(func.count(m.QuizResult.id)).filter(m.QuizResult.quiz_id == quiz_id).scalar() or 0


def max_score_of(db: Session, quiz_id: int) -> int:
    return db.query(func.coalesce(func.sum(m.QuizQuestion.points), 0)).filter(
        m.QuizQuestion.quiz_id == quiz_id).scalar() or 0


def question_count(db: Session, quiz_id: int) -> int:
    return db.query(func.count(m.QuizQuestion.id)).filter(m.QuizQuestion.quiz_id == quiz_id).scalar() or 0


def gap_count_of(question: m.QuizQuestion) -> int:
    return len(set(GAP_PATTERN.findall(question.question_text)))


def ensure_not_locked(db: Session, quiz: m.Quiz) -> None:
    if attempt_count(db, quiz.id) > 0:
        raise HTTPException(status_code=409, detail="Quiz ist gesperrt, weil es schon Abgaben gibt")


def question_teacher_out(db: Session, q: m.QuizQuestion) -> QuestionTeacherOut:
    return QuestionTeacherOut(
        id=q.id, position=q.position, type=q.type, points=q.points, question_text=q.question_text,
        options=[OptionTeacherOut(id=o.id, option_text=o.option_text, is_correct=bool(o.is_correct),
                                  gap_index=o.gap_index, position=o.position) for o in get_options(db, q.id)])


def quiz_teacher_out(db: Session, quiz: m.Quiz) -> QuizTeacherOut:
    return QuizTeacherOut(
        id=quiz.id, class_subject_id=quiz.class_subject_id, title=quiz.title, description=quiz.description,
        is_published=bool(quiz.is_published), locked=attempt_count(db, quiz.id) > 0,
        max_score=max_score_of(db, quiz.id),
        questions=[question_teacher_out(db, q) for q in get_questions(db, quiz.id)])


def delete_questions(db: Session, question_ids: list[int]) -> None:
    """Fragen + Optionen loeschen (explizit, damit es auch ohne DB-CASCADE stimmt)."""
    if not question_ids:
        return
    db.query(m.QuizOption).filter(m.QuizOption.question_id.in_(question_ids)).delete(synchronize_session=False)
    db.query(m.QuizQuestion).filter(m.QuizQuestion.id.in_(question_ids)).delete(synchronize_session=False)


# =====================================================================
# Frage pruefen und speichern (mc / tf / gap)
# =====================================================================
def validate_and_build_options(data: QuestionIn) -> list[dict]:
    if data.type == "mc":
        opts = data.options or []
        if len(opts) < 2:
            raise HTTPException(status_code=400, detail="Multiple Choice braucht mindestens 2 Antworten")
        if not any(o.is_correct for o in opts):
            raise HTTPException(status_code=400, detail="Mindestens eine Antwort muss richtig sein")
        return [{"option_text": o.option_text.strip(), "is_correct": o.is_correct, "gap_index": None,
                 "position": i + 1} for i, o in enumerate(opts)]

    if data.type == "tf":
        if data.correct is None:
            raise HTTPException(status_code=400, detail="Wahr/Falsch braucht 'correct': true oder false")
        return [{"option_text": "Wahr", "is_correct": data.correct is True, "gap_index": None, "position": 1},
                {"option_text": "Falsch", "is_correct": data.correct is False, "gap_index": None, "position": 2}]

    # gap
    found = sorted({int(n) for n in GAP_PATTERN.findall(data.question_text)})
    gaps = data.gaps or []
    if not found:
        raise HTTPException(status_code=400, detail="Lueckentext braucht mindestens eine Luecke {{0}} im Text")
    if found != list(range(len(found))):
        raise HTTPException(status_code=400, detail="Luecken muessen bei {{0}} beginnen und fortlaufend sein")
    if len(gaps) != len(found):
        raise HTTPException(status_code=400, detail=f"Text hat {len(found)} Luecke(n), aber {len(gaps)} Antwortlisten")
    options = []
    for gi, accepted in enumerate(gaps):
        cleaned = [a.strip() for a in accepted if a and a.strip()]
        if not cleaned:
            raise HTTPException(status_code=400, detail=f"Luecke {{{{{gi}}}}} braucht mindestens eine Antwort")
        for pi, text in enumerate(cleaned):
            if len(text) > 500:
                raise HTTPException(status_code=400, detail="Antwort zu lang (max. 500 Zeichen)")
            options.append({"option_text": text, "is_correct": True, "gap_index": gi, "position": pi + 1})
    return options


def save_options(db: Session, question_id: int, options: list[dict]) -> None:
    for o in options:
        db.add(m.QuizOption(question_id=question_id, **o))


# =====================================================================
# 1. + 2.  /subjects/{cs_id}/quizzes
# =====================================================================
@router.get("/subjects/{cs_id}/quizzes",
            response_model=list[QuizListTeacherOut] | list[QuizListStudentOut])
def list_quizzes(cs_id: int, db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    cs = db.get(m.ClassSubject, cs_id)
    if cs is None:
        raise HTTPException(status_code=404, detail="Fach nicht gefunden")
    quizzes = (db.query(m.Quiz).filter(m.Quiz.class_subject_id == cs_id)
               .order_by(m.Quiz.created_at.desc(), m.Quiz.id.desc()).all())

    if is_teacher_of(current, cs):
        result = []
        for q in quizzes:
            attempts = attempt_count(db, q.id)
            result.append(QuizListTeacherOut(
                id=q.id, title=q.title, description=q.description, is_published=bool(q.is_published),
                locked=attempts > 0, question_count=question_count(db, q.id), max_score=max_score_of(db, q.id),
                attempt_count=attempts, created_at=q.created_at))
        return result

    if role_of(current) == "schueler" and is_enrolled(db, current.id, cs_id):
        result = []
        for q in quizzes:
            own = get_result(db, q.id, current.id)
            # veroeffentlicht ODER schon abgegeben (damit das Ergebnis sichtbar bleibt)
            if not q.is_published and own is None:
                continue
            result.append(QuizListStudentOut(
                id=q.id, title=q.title, description=q.description, question_count=question_count(db, q.id),
                max_score=max_score_of(db, q.id),
                my_result=MyResultShortOut(score=own.score, max_score=own.max_score or max_score_of(db, q.id),
                                           submitted_at=own.submitted_at) if own else None))
        return result

    raise HTTPException(status_code=404, detail="Fach nicht gefunden")


@router.post("/subjects/{cs_id}/quizzes", response_model=QuizTeacherOut, status_code=201)
def create_quiz(cs_id: int, data: QuizCreateIn, db: Session = Depends(get_db),
                current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    cs = teacher_cs_or_404(db, cs_id, current)
    quiz = m.Quiz(class_subject_id=cs.id, created_by=current.id, title=data.title.strip(),
                  description=(data.description or "").strip() or None, is_published=False)
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz_teacher_out(db, quiz)


# =====================================================================
# 3. 4. 5.  /quizzes/{id}  (Lehrkraft)
# =====================================================================
@router.get("/quizzes/{quiz_id}", response_model=QuizTeacherOut)
def get_quiz(quiz_id: int, db: Session = Depends(get_db),
             current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    return quiz_teacher_out(db, teacher_quiz_or_404(db, quiz_id, current))


@router.put("/quizzes/{quiz_id}", response_model=QuizTeacherOut)
def update_quiz(quiz_id: int, data: QuizUpdateIn, db: Session = Depends(get_db),
                current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    quiz = teacher_quiz_or_404(db, quiz_id, current)
    new_title = data.title.strip() if data.title is not None else None
    new_desc = ((data.description or "").strip() or None) if data.description is not None else None
    changes_content = ((new_title is not None and new_title != quiz.title)
                       or (data.description is not None and new_desc != quiz.description))
    if changes_content:
        ensure_not_locked(db, quiz)
        if new_title is not None:
            quiz.title = new_title
        if data.description is not None:
            quiz.description = new_desc
    if data.is_published is not None:
        if data.is_published and question_count(db, quiz.id) == 0:
            raise HTTPException(status_code=400, detail="Ein Quiz ohne Fragen kann nicht veroeffentlicht werden")
        quiz.is_published = data.is_published
    db.commit()
    db.refresh(quiz)
    return quiz_teacher_out(db, quiz)


@router.delete("/quizzes/{quiz_id}")
def delete_quiz(quiz_id: int, db: Session = Depends(get_db),
                current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    quiz = teacher_quiz_or_404(db, quiz_id, current)
    ensure_not_locked(db, quiz)
    delete_questions(db, [q.id for q in get_questions(db, quiz.id)])
    db.delete(quiz)
    db.commit()
    return {"status": "geloescht", "id": quiz_id}


# =====================================================================
# 6. 7.  Fragen
# =====================================================================
@router.post("/quizzes/{quiz_id}/questions", response_model=QuestionTeacherOut, status_code=201)
def add_question(quiz_id: int, data: QuestionIn, db: Session = Depends(get_db),
                 current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    quiz = teacher_quiz_or_404(db, quiz_id, current)
    ensure_not_locked(db, quiz)
    options = validate_and_build_options(data)
    last = db.query(func.coalesce(func.max(m.QuizQuestion.position), 0)).filter(
        m.QuizQuestion.quiz_id == quiz.id).scalar() or 0
    q = m.QuizQuestion(quiz_id=quiz.id, position=last + 1, type=data.type,
                       question_text=data.question_text.strip(), points=data.points)
    db.add(q)
    db.flush()
    save_options(db, q.id, options)
    db.commit()
    db.refresh(q)
    return question_teacher_out(db, q)


def teacher_question_or_404(db: Session, question_id: int, user: m.User) -> tuple[m.QuizQuestion, m.Quiz]:
    q = db.get(m.QuizQuestion, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Frage nicht gefunden")
    quiz = teacher_quiz_or_404(db, q.quiz_id, user)
    return q, quiz


@router.put("/questions/{question_id}", response_model=QuestionTeacherOut)
def update_question(question_id: int, data: QuestionIn, db: Session = Depends(get_db),
                    current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    q, quiz = teacher_question_or_404(db, question_id, current)
    ensure_not_locked(db, quiz)
    options = validate_and_build_options(data)
    db.query(m.QuizOption).filter(m.QuizOption.question_id == q.id).delete(synchronize_session=False)
    q.type, q.question_text, q.points = data.type, data.question_text.strip(), data.points
    save_options(db, q.id, options)
    db.commit()
    db.refresh(q)
    return question_teacher_out(db, q)


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db),
                    current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    q, quiz = teacher_question_or_404(db, question_id, current)
    ensure_not_locked(db, quiz)
    delete_questions(db, [q.id])
    # ein veroeffentlichtes Quiz darf nicht leer sein
    if quiz.is_published and question_count(db, quiz.id) == 0:
        quiz.is_published = False
    db.commit()
    return {"status": "geloescht", "id": question_id}


# =====================================================================
# 8. 9. 10.  SchuelerIn: loesen, abgeben, Ergebnis
# =====================================================================
@router.get("/quizzes/{quiz_id}/take", response_model=QuizTakeOut)
def take_quiz(quiz_id: int, db: Session = Depends(get_db),
              current: m.User = Depends(require_roles("schueler"))):
    quiz = student_quiz_or_404(db, quiz_id, current)
    if get_result(db, quiz.id, current.id):
        raise HTTPException(status_code=409, detail="Dieses Quiz wurde bereits abgegeben")
    questions = []
    for q in get_questions(db, quiz.id):
        if q.type == "gap":
            # KEINE Loesungen: nur Text mit {{n}} und Anzahl der Luecken
            questions.append(QuestionStudentOut(id=q.id, position=q.position, type=q.type, points=q.points,
                                                question_text=q.question_text, gap_count=gap_count_of(q)))
        else:
            # KEIN is_correct
            questions.append(QuestionStudentOut(
                id=q.id, position=q.position, type=q.type, points=q.points, question_text=q.question_text,
                options=[OptionStudentOut(id=o.id, option_text=o.option_text) for o in get_options(db, q.id)]))
    return QuizTakeOut(id=quiz.id, title=quiz.title, description=quiz.description,
                       max_score=max_score_of(db, quiz.id), questions=questions)


def normalize(text: str) -> str:
    """Leerzeichen am Rand und Gross-/Kleinschreibung ignorieren."""
    return " ".join(text.strip().split()).casefold()


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizResultOut, status_code=201)
def submit_quiz_answers(quiz_id: int, data: QuizSubmitAnswersIn, db: Session = Depends(get_db),
                        current: m.User = Depends(require_roles("schueler"))):
    quiz = student_quiz_or_404(db, quiz_id, current)
    if get_result(db, quiz.id, current.id):
        raise HTTPException(status_code=409, detail="Dieses Quiz wurde bereits abgegeben")

    questions = get_questions(db, quiz.id)
    if not questions:
        raise HTTPException(status_code=400, detail="Quiz hat keine Fragen")
    by_id = {q.id: q for q in questions}
    answers = {}
    for a in data.answers:
        if a.question_id not in by_id:
            raise HTTPException(status_code=400, detail=f"Frage {a.question_id} gehoert nicht zu diesem Quiz")
        if a.question_id in answers:
            raise HTTPException(status_code=400, detail=f"Frage {a.question_id} wurde doppelt beantwortet")
        answers[a.question_id] = a

    # ---------- bewerten ----------
    score, max_score = 0, 0
    graded = []          # (frage, richtig?, antwort-zeilen)
    for q in questions:
        max_score += q.points
        options = get_options(db, q.id)
        a = answers.get(q.id)
        rows, correct = [], False

        if q.type in ("mc", "tf"):
            chosen = set(a.option_ids or []) if a else set()
            valid = {o.id for o in options}
            if not chosen <= valid:
                raise HTTPException(status_code=400, detail=f"Antwort gehoert nicht zu Frage {q.id}")
            right = {o.id for o in options if o.is_correct}
            correct = bool(chosen) and chosen == right            # genau die richtigen, nicht mehr/weniger
            rows = [{"option_id": oid, "is_correct": correct} for oid in sorted(chosen)]
        else:  # gap
            n = gap_count_of(q)
            given = list(a.gaps or []) if a else []
            if len(given) > n:
                raise HTTPException(status_code=400, detail=f"Frage {q.id} hat nur {n} Luecke(n)")
            per_gap = []
            for gi in range(n):
                text = given[gi] if gi < len(given) else ""
                accepted = {normalize(o.option_text) for o in options if o.gap_index == gi}
                ok = bool(text.strip()) and normalize(text) in accepted
                per_gap.append(ok)
                if text.strip():
                    rows.append({"gap_index": gi, "text_answer": text.strip()[:500], "is_correct": ok})
            correct = n > 0 and all(per_gap)

        if correct:
            score += q.points
        graded.append((q, correct, rows))

    # ---------- speichern (eine Transaktion) ----------
    result = m.QuizResult(quiz_id=quiz.id, student_id=current.id, score=score, max_score=max_score)
    db.add(result)
    try:
        db.flush()
        for q, _, rows in graded:
            for r in rows:
                db.add(m.QuizAnswer(result_id=result.id, question_id=q.id, **r))
        db.commit()
    except IntegrityError:          # gleichzeitig zweimal abgeschickt -> UNIQUE(quiz_id, student_id)
        db.rollback()
        raise HTTPException(status_code=409, detail="Dieses Quiz wurde bereits abgegeben")
    db.refresh(result)

    return QuizResultOut(score=score, max_score=max_score, submitted_at=result.submitted_at, questions=[
        QuestionResultOut(question_id=q.id, question_text=q.question_text, correct=c,
                          points_awarded=q.points if c else 0) for q, c, _ in graded])


@router.get("/quizzes/{quiz_id}/my-result", response_model=QuizResultOut)
def my_result(quiz_id: int, db: Session = Depends(get_db),
              current: m.User = Depends(require_roles("schueler"))):
    quiz = student_quiz_or_404(db, quiz_id, current, allow_unpublished_with_result=True)
    result = get_result(db, quiz.id, current.id)
    if result is None:
        raise HTTPException(status_code=404, detail="Noch nicht abgegeben")
    rows = db.query(m.QuizAnswer).filter(m.QuizAnswer.result_id == result.id).all()
    out = []
    for q in get_questions(db, quiz.id):
        q_rows = [r for r in rows if r.question_id == q.id]
        if q.type == "gap":
            n = gap_count_of(q)
            correct = n > 0 and len([r for r in q_rows if r.is_correct]) == n
        else:
            correct = bool(q_rows) and all(r.is_correct for r in q_rows)
        out.append(QuestionResultOut(question_id=q.id, question_text=q.question_text, correct=correct,
                                     points_awarded=q.points if correct else 0))
    return QuizResultOut(score=result.score, max_score=result.max_score or max_score_of(db, quiz.id),
                         submitted_at=result.submitted_at, questions=out)


# =====================================================================
# 11.  Ergebnisse aller SchuelerInnen (Lehrkraft)
# =====================================================================
@router.get("/quizzes/{quiz_id}/attempts", response_model=list[AttemptOut])
def list_attempts(quiz_id: int, db: Session = Depends(get_db),
                  current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    quiz = teacher_quiz_or_404(db, quiz_id, current)
    rows = (db.query(m.QuizResult, m.User).join(m.User, m.User.id == m.QuizResult.student_id)
            .filter(m.QuizResult.quiz_id == quiz.id).order_by(m.User.last_name, m.User.first_name).all())
    return [AttemptOut(student_id=u.id, first_name=u.first_name, last_name=u.last_name, username=u.username,
                       score=r.score, max_score=r.max_score, submitted_at=r.submitted_at) for r, u in rows]
