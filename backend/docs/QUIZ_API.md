# Quiz-API – Vertrag zwischen WebApp und REST-API

Stand: 13.10.2026 · Status: **festgelegt, API wird gebaut** (Schema V4.4, `sql/migration_v4_4_quiz.sql`)
Diese Formate gelten. Die WebApp kann damit sofort mit Testdaten (Mock) arbeiten.

Alle Requests mit `Authorization: Bearer <token>`. Rollen wie bisher: `schueler`, `lehrkraft`, `admin`.
„Fach“ = `class_subjects.id` (wie bei `/subjects/{id}`).

## Grundregeln

1. **Die richtigen Antworten verlassen nie den Server für Schüler.** `/take` liefert kein `is_correct` und keine Lücken-Lösungen.
2. **Die API bewertet**, nicht die WebApp. Der Schüler schickt nur seine Antworten.
3. Jede Frage zählt **ganz oder gar nicht** (`points` oder 0). Punkte sind ganze Zahlen.
4. **Sobald es eine Abgabe gibt, ist das Quiz gesperrt** (`locked: true`): Fragen ändern/löschen und Quiz löschen → `409`.
   Nur `is_published` darf dann noch umgeschaltet werden (z. B. Quiz wieder ausblenden).
5. Lehrkraft: nur Quizzes in **eigenen** Fächern. Schüler: nur **veröffentlichte** Quizzes in Fächern, in denen er eingetragen ist.
   Kein Zugriff → `404` (wie bei Fächern).
6. Jeder Schüler kann ein Quiz **einmal** abgeben (zweites Mal → `409`).

## Fragetypen

| `type` | Bedeutung | So legt die Lehrkraft sie an |
|---|---|---|
| `mc` | Multiple Choice (eine oder mehrere richtige Antworten) | `options: [{option_text, is_correct}]`, mind. 2 Optionen, mind. 1 richtig |
| `tf` | Wahr/Falsch | `correct: true` oder `false` (die API legt die Optionen „Wahr“/„Falsch“ selbst an) |
| `gap` | Lückentext | Im Text Lücken als `{{0}}`, `{{1}}` …; `gaps: [["Wien"], ["Graz","Grätz"]]` = akzeptierte Antworten pro Lücke |

**Bewertung:**
- `mc`/`tf`: richtig, wenn die gewählten Optionen **genau** den richtigen entsprechen (nicht mehr, nicht weniger).
- `gap`: richtig, wenn **jede** Lücke einer akzeptierten Antwort entspricht – Leerzeichen am Rand und Groß-/Kleinschreibung werden ignoriert.

---

## Endpunkte

### 1. `GET /subjects/{cs_id}/quizzes` – Liste (Lehrkraft und Schüler)

Lehrkraft (alle Quizzes ihres Fachs):
```json
[
  {
    "id": 3,
    "title": "Bruchrechnen",
    "description": "Kapitel 4",
    "is_published": true,
    "locked": true,
    "question_count": 5,
    "max_score": 8,
    "attempt_count": 12,
    "created_at": "2026-10-13T10:15:00"
  }
]
```
Schüler (nur veröffentlichte, mit eigenem Ergebnis oder `null`):
```json
[
  {
    "id": 3,
    "title": "Bruchrechnen",
    "description": "Kapitel 4",
    "question_count": 5,
    "max_score": 8,
    "my_result": { "score": 6, "max_score": 8, "submitted_at": "2026-10-13T11:02:41" }
  },
  {
    "id": 4,
    "title": "Prozentrechnung",
    "description": null,
    "question_count": 3,
    "max_score": 3,
    "my_result": null
  }
]
```

### 2. `POST /subjects/{cs_id}/quizzes` – Quiz anlegen (Lehrkraft des Fachs)
```json
{ "title": "Bruchrechnen", "description": "Kapitel 4" }
```
→ `201` mit dem Quiz wie in **3.** (`is_published: false`, `questions: []`).
`title` 1–150 Zeichen, `description` optional.

### 3. `GET /quizzes/{id}` – Quiz mit Lösungen (nur Lehrkraft des Fachs)
```json
{
  "id": 3,
  "class_subject_id": 2,
  "title": "Bruchrechnen",
  "description": "Kapitel 4",
  "is_published": false,
  "locked": false,
  "max_score": 4,
  "questions": [
    {
      "id": 10, "position": 1, "type": "mc", "points": 2,
      "question_text": "Welche Brüche sind gleich 1/2?",
      "options": [
        { "id": 31, "option_text": "2/4", "is_correct": true,  "gap_index": null, "position": 1 },
        { "id": 32, "option_text": "3/4", "is_correct": false, "gap_index": null, "position": 2 },
        { "id": 33, "option_text": "4/8", "is_correct": true,  "gap_index": null, "position": 3 }
      ]
    },
    {
      "id": 11, "position": 2, "type": "tf", "points": 1,
      "question_text": "1/3 ist größer als 1/4.",
      "options": [
        { "id": 34, "option_text": "Wahr",   "is_correct": true,  "gap_index": null, "position": 1 },
        { "id": 35, "option_text": "Falsch", "is_correct": false, "gap_index": null, "position": 2 }
      ]
    },
    {
      "id": 12, "position": 3, "type": "gap", "points": 1,
      "question_text": "3/4 als Dezimalzahl ist {{0}}.",
      "options": [
        { "id": 36, "option_text": "0,75", "is_correct": true, "gap_index": 0, "position": 1 },
        { "id": 37, "option_text": "0.75", "is_correct": true, "gap_index": 0, "position": 2 }
      ]
    }
  ]
}
```

### 4. `PUT /quizzes/{id}` – Quiz ändern / veröffentlichen (Lehrkraft)
Alle Felder optional:
```json
{ "title": "Bruchrechnen (neu)", "description": "Kapitel 4+5", "is_published": true }
```
→ `200` mit Quiz wie in **3.**
- `locked` und Titel/Beschreibung ändern → `409`
- Veröffentlichen ohne Fragen → `400`

### 5. `DELETE /quizzes/{id}` – Quiz löschen (Lehrkraft)
→ `200 {"status": "geloescht", "id": 3}` · mit Abgaben (`locked`) → `409`

### 6. `POST /quizzes/{id}/questions` – Frage hinzufügen (Lehrkraft)
Je nach Typ:
```json
{ "type": "mc", "question_text": "Welche Brüche sind gleich 1/2?", "points": 2,
  "options": [ {"option_text": "2/4", "is_correct": true}, {"option_text": "3/4", "is_correct": false}, {"option_text": "4/8", "is_correct": true} ] }
```
```json
{ "type": "tf", "question_text": "1/3 ist größer als 1/4.", "points": 1, "correct": true }
```
```json
{ "type": "gap", "question_text": "3/4 als Dezimalzahl ist {{0}}.", "points": 1, "gaps": [["0,75", "0.75"]] }
```
→ `201` mit der Frage wie in **3.** (wird hinten angehängt) · `points` 1–100 · `locked` → `409`
- Anzahl `gaps` muss zu den `{{n}}` im Text passen → sonst `400`

### 7. `PUT /questions/{id}` und `DELETE /questions/{id}` (Lehrkraft)
`PUT`: gleicher Body wie **6.**, ersetzt die Frage komplett (inkl. Optionen) → `200`
`DELETE` → `200` · beides bei `locked` → `409`

### 8. `GET /quizzes/{id}/take` – Quiz zum Lösen (Schüler)
**Ohne Lösungen.** Bei `gap`: Text mit `{{n}}` und nur die Anzahl der Lücken.
```json
{
  "id": 3,
  "title": "Bruchrechnen",
  "description": "Kapitel 4",
  "max_score": 4,
  "questions": [
    { "id": 10, "position": 1, "type": "mc", "points": 2, "question_text": "Welche Brüche sind gleich 1/2?",
      "options": [ {"id": 31, "option_text": "2/4"}, {"id": 32, "option_text": "3/4"}, {"id": 33, "option_text": "4/8"} ] },
    { "id": 11, "position": 2, "type": "tf", "points": 1, "question_text": "1/3 ist größer als 1/4.",
      "options": [ {"id": 34, "option_text": "Wahr"}, {"id": 35, "option_text": "Falsch"} ] },
    { "id": 12, "position": 3, "type": "gap", "points": 1, "question_text": "3/4 als Dezimalzahl ist {{0}}.",
      "gap_count": 1 }
  ]
}
```
Schon abgegeben → `409` · nicht veröffentlicht / nicht im Fach → `404`

### 9. `POST /quizzes/{id}/submit` – Abgeben (Schüler)
```json
{
  "answers": [
    { "question_id": 10, "option_ids": [31, 33] },
    { "question_id": 11, "option_ids": [34] },
    { "question_id": 12, "gaps": ["0,75"] }
  ]
}
```
Nicht beantwortete Fragen dürfen fehlen (zählen 0 Punkte).
→ `201`:
```json
{
  "score": 4,
  "max_score": 4,
  "submitted_at": "2026-10-13T11:02:41",
  "questions": [
    { "question_id": 10, "correct": true, "points_awarded": 2 },
    { "question_id": 11, "correct": true, "points_awarded": 1 },
    { "question_id": 12, "correct": true, "points_awarded": 1 }
  ]
}
```
Die richtigen Lösungen werden auch hier **nicht** mitgeschickt, nur richtig/falsch pro Frage.
Zweite Abgabe → `409` · `question_id` gehört nicht zum Quiz / Option gehört nicht zur Frage → `400`

### 10. `GET /quizzes/{id}/my-result` – Eigenes Ergebnis (Schüler)
→ `200`, gleiches Format wie die Antwort von **9.** · noch nicht abgegeben → `404`

### 11. `GET /quizzes/{id}/attempts` – Ergebnisse aller Schüler (Lehrkraft)
```json
[
  { "student_id": 8, "first_name": "Test", "last_name": "Schueler", "username": "tschueler",
    "score": 3, "max_score": 4, "submitted_at": "2026-10-13T11:02:41" }
]
```

---

## Hinweis zum alten Endpunkt

`POST /quiz/submit` (Ziel-M-4) nimmt den Score vom Client an – ein Schüler könnte sich damit selbst Punkte geben.
Die WebApp verwendet **nur noch Endpunkt 9**. Der alte Endpunkt wird für Quizzes mit Fragen gesperrt.

## Fehlercodes
`400` ungültige Eingabe · `401` nicht eingeloggt · `403` falsche Rolle · `404` nicht gefunden / kein Zugriff ·
`409` gesperrt (Abgaben vorhanden) oder schon abgegeben · `422` Feld fehlt / falscher Typ
