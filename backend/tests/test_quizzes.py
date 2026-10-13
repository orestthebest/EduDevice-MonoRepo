"""
Tests Quiz-System (V4.4) - prueft die Regeln aus docs/QUIZ_API.md
Testdaten: alehrer (Lehrkraft Mathe 4A = class_subject 1), tschueler (in Mathe eingetragen)
"""

import pytest


@pytest.fixture(scope="module")
def quiz(client, teacher):
    """Quiz mit je einer Frage pro Typ: mc (2 P.), tf (1 P.), gap (1 P.) = max 4."""
    r = client.post("/subjects/1/quizzes", json={"title": "Bruchrechnen", "description": "Kapitel 4"}, headers=teacher)
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    assert r.json()["is_published"] is False and r.json()["questions"] == []

    mc = client.post(f"/quizzes/{qid}/questions", headers=teacher, json={
        "type": "mc", "question_text": "Welche Brueche sind gleich 1/2?", "points": 2,
        "options": [{"option_text": "2/4", "is_correct": True}, {"option_text": "3/4", "is_correct": False},
                    {"option_text": "4/8", "is_correct": True}]})
    tf = client.post(f"/quizzes/{qid}/questions", headers=teacher, json={
        "type": "tf", "question_text": "1/3 ist groesser als 1/4.", "points": 1, "correct": True})
    gap = client.post(f"/quizzes/{qid}/questions", headers=teacher, json={
        "type": "gap", "question_text": "3/4 als Dezimalzahl ist {{0}}.", "points": 1, "gaps": [["0,75", "0.75"]]})
    for x in (mc, tf, gap):
        assert x.status_code == 201, x.text
    return {"id": qid, "mc": mc.json(), "tf": tf.json(), "gap": gap.json()}


def option_ids(question, correct):
    return [o["id"] for o in question["options"] if o["is_correct"] == correct]


# ---------------- Lehrkraft ----------------
def test_quiz_detail_mit_loesungen(client, teacher, quiz):
    d = client.get(f"/quizzes/{quiz['id']}", headers=teacher).json()
    assert d["max_score"] == 4 and len(d["questions"]) == 3
    assert [q["position"] for q in d["questions"]] == [1, 2, 3]
    tf = d["questions"][1]
    assert [(o["option_text"], o["is_correct"]) for o in tf["options"]] == [("Wahr", True), ("Falsch", False)]


def test_ungueltige_fragen_400(client, teacher, quiz):
    url = f"/quizzes/{quiz['id']}/questions"
    bad = [
        {"type": "mc", "question_text": "x", "options": [{"option_text": "a", "is_correct": True}]},      # nur 1 Option
        {"type": "mc", "question_text": "x", "options": [{"option_text": "a"}, {"option_text": "b"}]},   # keine richtig
        {"type": "tf", "question_text": "x"},                                                             # correct fehlt
        {"type": "gap", "question_text": "ohne Luecke", "gaps": [["a"]]},
        {"type": "gap", "question_text": "{{0}} und {{1}}", "gaps": [["a"]]},                             # 2 Luecken, 1 Liste
        {"type": "gap", "question_text": "{{1}}", "gaps": [["a"]]},                                       # beginnt nicht bei 0
    ]
    for body in bad:
        assert client.post(url, json=body, headers=teacher).status_code == 400, body
    assert client.post(url, json={"type": "xy", "question_text": "x"}, headers=teacher).status_code == 422


def test_leeres_quiz_nicht_veroeffentlichen(client, teacher):
    qid = client.post("/subjects/1/quizzes", json={"title": "Leer"}, headers=teacher).json()["id"]
    assert client.put(f"/quizzes/{qid}", json={"is_published": True}, headers=teacher).status_code == 400
    assert client.delete(f"/quizzes/{qid}", headers=teacher).status_code == 200


def test_rechte(client, teacher, student, admin, quiz):
    assert client.get(f"/quizzes/{quiz['id']}", headers=student).status_code == 403        # SchuelerIn: keine Loesungen
    assert client.post("/subjects/1/quizzes", json={"title": "x"}, headers=student).status_code == 403
    assert client.get(f"/quizzes/{quiz['id']}", headers=admin).status_code == 200
    assert client.get("/quizzes/999999", headers=teacher).status_code == 404


# ---------------- SchuelerIn vor Veroeffentlichung ----------------
def test_unveroeffentlicht_unsichtbar(client, student, quiz):
    ids = [q["id"] for q in client.get("/subjects/1/quizzes", headers=student).json()]
    assert quiz["id"] not in ids
    assert client.get(f"/quizzes/{quiz['id']}/take", headers=student).status_code == 404


def test_veroeffentlichen(client, teacher, quiz):
    r = client.put(f"/quizzes/{quiz['id']}", json={"is_published": True}, headers=teacher)
    assert r.status_code == 200 and r.json()["is_published"] is True


def test_take_ohne_loesungen(client, student, quiz):
    r = client.get(f"/quizzes/{quiz['id']}/take", headers=student)
    assert r.status_code == 200
    text = r.text
    assert "is_correct" not in text and "0,75" not in text and "0.75" not in text   # keine Loesungen
    gap = [q for q in r.json()["questions"] if q["type"] == "gap"][0]
    assert gap["gap_count"] == 1 and gap["options"] is None
    lst = client.get("/subjects/1/quizzes", headers=student).json()
    assert any(q["id"] == quiz["id"] and q["my_result"] is None for q in lst)


# ---------------- Abgabe + Bewertung ----------------
def test_abgabe_falsche_frage_400(client, student, quiz):
    r = client.post(f"/quizzes/{quiz['id']}/submit", headers=student,
                    json={"answers": [{"question_id": 999999, "option_ids": [1]}]})
    assert r.status_code == 400
    r = client.post(f"/quizzes/{quiz['id']}/submit", headers=student,
                    json={"answers": [{"question_id": quiz["mc"]["id"], "option_ids": option_ids(quiz["tf"], True)}]})
    assert r.status_code == 400   # Option gehoert zu anderer Frage


def test_abgabe_und_bewertung(client, student, quiz):
    """mc nur teilweise richtig (0 P.), tf richtig (1 P.), gap mit Grossbuchst./Leerzeichen richtig (1 P.)."""
    body = {"answers": [
        {"question_id": quiz["mc"]["id"], "option_ids": option_ids(quiz["mc"], True)[:1]},   # nur 1 von 2 richtigen
        {"question_id": quiz["tf"]["id"], "option_ids": option_ids(quiz["tf"], True)},
        {"question_id": quiz["gap"]["id"], "gaps": ["  0,75 "]},
    ]}
    r = client.post(f"/quizzes/{quiz['id']}/submit", json=body, headers=student)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["score"] == 2 and j["max_score"] == 4
    assert [q["correct"] for q in j["questions"]] == [False, True, True]
    assert all("question_text" in q for q in j["questions"])
    assert "is_correct" not in r.text


def test_zweite_abgabe_409(client, student, quiz):
    assert client.post(f"/quizzes/{quiz['id']}/submit", json={"answers": []}, headers=student).status_code == 409
    assert client.get(f"/quizzes/{quiz['id']}/take", headers=student).status_code == 409


def test_my_result(client, student, quiz):
    j = client.get(f"/quizzes/{quiz['id']}/my-result", headers=student).json()
    assert j["score"] == 2 and [q["correct"] for q in j["questions"]] == [False, True, True]
    assert j["questions"][0]["question_text"].startswith("Welche")


def test_gesperrt_nach_abgabe(client, teacher, quiz):
    d = client.get(f"/quizzes/{quiz['id']}", headers=teacher).json()
    assert d["locked"] is True
    assert client.post(f"/quizzes/{quiz['id']}/questions", headers=teacher,
                       json={"type": "tf", "question_text": "x", "correct": True}).status_code == 409
    assert client.delete(f"/questions/{quiz['tf']['id']}", headers=teacher).status_code == 409
    assert client.put(f"/quizzes/{quiz['id']}", json={"title": "Neu"}, headers=teacher).status_code == 409
    assert client.delete(f"/quizzes/{quiz['id']}", headers=teacher).status_code == 409


def test_ergebnis_bleibt_nach_ausblenden(client, teacher, student, quiz):
    assert client.put(f"/quizzes/{quiz['id']}", json={"is_published": False}, headers=teacher).status_code == 200
    lst = client.get("/subjects/1/quizzes", headers=student).json()
    mine = [q for q in lst if q["id"] == quiz["id"]]
    assert mine and mine[0]["my_result"]["score"] == 2          # Orests Wunsch: Ergebnis bleibt sichtbar
    assert client.get(f"/quizzes/{quiz['id']}/my-result", headers=student).status_code == 200
    assert client.get(f"/quizzes/{quiz['id']}/take", headers=student).status_code == 404


def test_attempts_und_lehrerliste(client, teacher, quiz):
    att = client.get(f"/quizzes/{quiz['id']}/attempts", headers=teacher).json()
    assert len(att) == 1 and att[0]["username"] == "tschueler" and att[0]["score"] == 2
    lst = client.get("/subjects/1/quizzes", headers=teacher).json()
    q = [x for x in lst if x["id"] == quiz["id"]][0]
    assert q["attempt_count"] == 1 and q["locked"] is True and q["max_score"] == 4 and q["question_count"] == 3


def test_alter_submit_gesperrt_fuer_quiz_mit_fragen(client, student, quiz):
    r = client.post("/quiz/submit", json={"quiz_id": quiz["id"], "score": 100}, headers=student)
    assert r.status_code == 409


def test_frage_bearbeiten_vor_abgabe(client, teacher):
    qid = client.post("/subjects/1/quizzes", json={"title": "Edit"}, headers=teacher).json()["id"]
    q = client.post(f"/quizzes/{qid}/questions", headers=teacher,
                    json={"type": "tf", "question_text": "a", "correct": True}).json()
    r = client.put(f"/questions/{q['id']}", headers=teacher,
                   json={"type": "gap", "question_text": "{{0}} + {{1}}", "gaps": [["1"], ["2", "zwei"]]})
    assert r.status_code == 200 and r.json()["type"] == "gap" and len(r.json()["options"]) == 3
    assert client.delete(f"/questions/{q['id']}", headers=teacher).status_code == 200
    assert client.delete(f"/quizzes/{qid}", headers=teacher).status_code == 200
