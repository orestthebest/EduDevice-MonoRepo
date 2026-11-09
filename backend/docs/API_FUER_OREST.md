# EduDevice REST-API V2.10 – Anleitung für die WebApp

Basis-URL am Server (nur intern): `http://127.0.0.1:8000`  ·  Swagger: `http://172.20.1.115:8000/docs`
Alle Endpunkte außer Login/Register brauchen den Header `Authorization: Bearer <token>`.
Rollen wie in der DB: `schueler`, `lehrkraft`, `admin`.

## Welche Funktion wird durch welchen Endpunkt ersetzt

| Orest (alt, direktes SQL) | Neu (REST-API) | Wer |
|---|---|---|
| `login/+page.server.js` SELECT users + `createSession` | `POST /auth/login` (Form: username, password) → `access_token`, `role`, ... | alle |
| Rolle im Login-Formular prüfen | Antwort-Feld `role` mit gewählter Rolle vergleichen | – |
| `register/+page.server.js` INSERT users | `POST /auth/register` JSON `{first_name,last_name,username,email,password,role}` role = `schueler`/`lehrkraft` | alle |
| `validateSession` (hooks.server.js) | `GET /auth/me` mit Token aus Cookie | alle |
| `invalidateSession` (Logout) | nur Cookie löschen (JWT ist zustandslos) | – |
| `getClasses` | `GET /classes` | lehrkraft, admin |
| `getClass` | `GET /classes/{id}` | admin |
| `getClassStudents` | `GET /classes/{id}/students` | admin |
| `getAssignableStudents` | `GET /classes/{id}/assignable-students` | admin |
| `addStudentToClass` | `POST /classes/{id}/students` JSON `{student_id}` | admin |
| `removeStudentFromClass` | `DELETE /classes/{id}/students/{student_id}` | admin |
| `getSubjectsForUser` | `GET /subjects` | alle (gefiltert nach Rolle) |
| `getSubjectNames` | `GET /subjects/names` | lehrkraft, admin |
| `createClassSubject` | `POST /subjects` JSON `{class_id, name}` | lehrkraft |
| `getClassSubjectForUser` | `GET /subjects/{id}` (404 wenn kein Zugriff) | alle |
| `deleteClassSubject` | `DELETE /subjects/{id}` (409 wenn Noten/Quiz/Hausübung/Stundenplan dranhängen) | lehrkraft des Fachs |
| `getSubjectStudents` | `GET /subjects/{id}/students` | lehrkraft des Fachs |
| `getAddableStudents` | `GET /subjects/{id}/addable-students` | lehrkraft des Fachs |
| `addStudent` | `POST /subjects/{id}/students` JSON `{student_id}` | lehrkraft des Fachs |
| `removeStudent` | `DELETE /subjects/{id}/students/{student_id}` | lehrkraft des Fachs |
| `getMaterials` | `GET /subjects/{id}/materials` | alle mit Zugriff |
| `saveFile` + `insertMaterial` | `POST /subjects/{id}/materials` multipart: `title`, `file` | lehrkraft des Fachs |
| `deleteMaterial` + `deleteFile` | `DELETE /subjects/{id}/materials/{material_id}` | lehrkraft des Fachs |
| `ALLOWED_EXTENSIONS`, `MAX_SIZE` (files.js) | `GET /materials/config` → `{allowed_extensions, max_size_mb}` | alle |
| `getRecentMaterials` | `GET /materials/recent?limit=6` | alle |
| `materials/[id]/+server.js` | `GET /materials/{id}/download` (Datei durchreichen) | alle mit Zugriff |

Die Feldnamen in den Antworten sind dieselben wie in Orests SQL (`subject_name`, `class_name`,
`teacher_name`, `file_count`, `student_count`, `original_name`, `size_bytes`, `uploaded_at`, `ext` ...),
damit die `.svelte`-Seiten fast nicht geändert werden müssen.

## Wichtig: echte IP mitschicken
Bei Login und Register immer `clientIp: event.getClientAddress()` mitgeben. Sonst kommen alle Anfragen von 127.0.0.1
und das Rate-Limit (Login 10/min, Register 5/min) gilt für **alle Benutzer zusammen**.

## Fehlercodes
`400` falsche Eingabe · `401` nicht eingeloggt / Token abgelaufen → zu `/login` · `403` keine Berechtigung ·
`404` nicht gefunden oder kein Zugriff · `409` Duplikat / blockiert · `413` Datei > 50 MB · `422` Feld fehlt/falsch · `429` zu viele Versuche

## Was im Frontend weg kann
`database.js`, `auth.js`, `classes.js`, `subjects.js`, `files.js` → ersetzt durch `api.js`
(Vorlage: `backend/docs/api_beispiel.js` → nach `frontend/src/lib/server/api.js` kopieren).
`mysql2` und `bcrypt` aus `package.json`, DB-Zugangsdaten aus `frontend/.env`.
Neu in `.env`: `API_URL=http://127.0.0.1:8000`.
Danach: MySQL-User `orest` wird gelöscht.

## Beispiel: Login-Action
```js
import { login } from '$lib/server/api.js';
const result = await login(username, password, getClientAddress()); // action bekommt { request, cookies, url, getClientAddress }
if (!result) return fail(400, { username, error: 'Wrong username or password' });
if (result.role !== role) return fail(400, { username, error: 'This account does not have the selected role' });
cookies.set('token', result.access_token, { path: '/', httpOnly: true, sameSite: 'lax',
  secure: url.protocol === 'https:', maxAge: 60 * 60 });
```

## Beispiel: hooks.server.js
```js
import { api } from '$lib/server/api.js';
export async function handle({ event, resolve }) {
  const token = event.cookies.get('token');
  event.locals.token = token ?? null;
  event.locals.user = null;
  if (token) {
    const res = await api('/auth/me', { token });
    if (res.ok) event.locals.user = await res.json();
    else event.cookies.delete('token', { path: '/' });
  }
  return resolve(event);
}
```

## Beispiel: Upload weiterreichen
```js
const form = await request.formData();           // enthält title + file
const res = await api(`/subjects/${params.id}/materials`, { method: 'POST', token: locals.token, form });
if (!res.ok) return fail(res.status, { error: (await res.json()).detail });
```

## Benutzerprofil (V2.5, Schema V4.5)

Die User-ID kommt immer aus dem JWT, nie aus dem Request. `GET /auth/me` liefert jetzt zusätzlich
`profile_image` (Dateiname oder `null`).

| Methode + Pfad | Body | Antwort |
|---|---|---|
| `PATCH /users/me` | JSON `{ "email": "..." }` | `200` UserOut · `409` E-Mail vergeben · `422` ungültig |
| `POST /users/me/avatar` | multipart, Feld `file` (jpg/png/webp, max. 2 MB) | `200 { "profile_image": "8-1761680000000.webp" }` · `413` zu groß · `400` falscher Typ / kaputtes Bild |
| `DELETE /users/me/avatar` | – | `204` (auch wenn kein Bild da war) |
| `GET /users/avatar/{filename}` | – | Bild (`image/webp`), nur mit Token · `404` |

- Bei `PATCH /users/me` werden andere Felder (`role`, `username` …) ignoriert, nur die E-Mail wird geändert.
  Die E-Mail wird kleingeschrieben gespeichert; Leerzeichen am Rand → `422` (wie bei Register), also im Frontend `trim()`.
- Der Typ wird am echten Bildinhalt geprüft, nicht an der Endung. Das Bild wird mittig quadratisch
  auf 256×256 zugeschnitten und als WebP gespeichert; das alte Bild wird gelöscht.
- Jeder Upload bekommt einen neuen Dateinamen → kein Browser-Cache-Problem nach einem neuen Bild.
- `GET /users/avatar/...` braucht den Bearer-Token. Ein `<img src>` direkt auf die API schickt keinen
  Token mit → das Bild über eine SvelteKit-Route weiterreichen:

```js
// src/routes/avatar/[file]/+server.js
import { api } from '$lib/server/api.js';
import { error } from '@sveltejs/kit';
export async function GET({ params, locals }) {
  if (!locals.token) error(401, 'Nicht eingeloggt');
  const res = await api(`/users/avatar/${encodeURIComponent(params.file)}`, { token: locals.token });
  if (!res.ok) error(res.status, 'Bild nicht gefunden');
  return new Response(res.body, { headers: { 'Content-Type': 'image/webp', 'Cache-Control': 'private, max-age=86400' } });
}
```

## Entschuldigungssystem (V2.6, Schema V4.6)

Fehlstunde = `attendance`-Zeile mit `status` `abwesend` oder `verspaetet`. Die Verbindung zur Entschuldigung
steht in `attendance.excuse_id` (keine Extra-Tabelle). **Unentschuldigt** = keine Entschuldigung oder abgelehnt;
abgelehnte Stunden können neu eingereicht werden. Stunden mit `lessons.cancelled = true` zählen nicht.
Klassenvorstand = `classes.class_teacher_id`, Klasse der SchülerIn über `student_classes`.

| Methode + Pfad | Rolle | Body / Query | Antwort |
|---|---|---|---|
| `GET /attendance/me?unexcused=true` | schueler | ohne `unexcused` → alle eigenen Fehlstunden | `[AbsenceOut]`, neueste zuerst |
| `POST /excuses` | schueler | `{ "reason": "...", "attendance_ids": [4, 5] }` | `201 ExcuseOut` · `400` fremde / schon entschuldigte Stunde |
| `GET /excuses/me` | schueler | – | `[ExcuseOut]`, neueste zuerst |
| `GET /excuses/class-teacher?status=pending` | lehrkraft (Klassenvorstand), admin (alle) | `status` optional | `[ExcuseOut]` mit `class_name` |
| `PATCH /excuses/{id}` | Klassenvorstand der SchülerIn, admin | `{ "status": "accepted" \| "rejected", "teacher_comment": "..." }` | `200 ExcuseOut` · `404` nicht mein Schüler · `409` schon bearbeitet |

```json
// AbsenceOut
{ "attendance_id": 4, "date": "2026-10-05", "start_time": "08:00:00", "end_time": "08:50:00",
  "subject_name": "Mathematik", "status": "abwesend", "excuse_id": 2, "excuse_status": "pending" }

// ExcuseOut
{ "id": 2, "student_id": 3, "student_name": "Test Schueler", "class_name": "4A",
  "date_from": "2026-10-05", "date_to": "2026-10-12", "reason": "Krank", "status": "rejected",
  "teacher_comment": "Bitte Arztbestätigung", "reviewed_by": 2, "reviewed_by_name": "Anna Lehrer",
  "reviewed_at": "2026-10-29T21:30:00", "submitted_at": "2026-10-29T20:00:00", "absences": [ AbsenceOut, ... ] }
```

- `date_from` / `date_to` setzt die API selbst (erste und letzte Stunde).
- `class_name` ist bei `/excuses/me` `null` (nur beim Klassenvorstand gefüllt).
- Wird eine abgelehnte Stunde neu eingereicht, wandert sie zur neuen Entschuldigung; die alte, abgelehnte
  zeigt dann weniger (oder keine) Stunden.
- Bearbeiten geht nur einmal (`pending` → `accepted`/`rejected`), danach `409`.
- Testdaten (`python -m scripts.seed`): Klassenvorstand der 4A ist `alehrer`, `tschueler` hat 3 Fehlstunden
  (05.10. abwesend, 12.10. verspätet, 19.10. abwesend).

## Registrierung nur für SchülerInnen (V2.7)

Vorher konnte sich jeder mit `"role": "lehrkraft"` selbst ein Lehrer-Konto anlegen und damit Noten eintragen.
Jetzt gilt:

| Methode + Pfad | Wer | Antwort |
|---|---|---|
| `POST /auth/register` | alle | nur SchülerIn. `role` darf fehlen (= `schueler`) · `"lehrkraft"` → `403` · `"admin"` → `422` |
| `POST /users` | nur admin | Body wie Register, `role`: `"schueler"` oder `"lehrkraft"` → `201` UserOut · `409` doppelt |

→ Auf der Registrierungsseite die Auswahl „Lehrkraft“ bitte entfernen (oder einfach kein `role` mitschicken).
Lehrkräfte legt der Admin an, z. B. über eine eigene Admin-Seite mit `POST /users`.

## Anwesenheit pro Stunde (V2.8)

**Wie eine Stunde im Schema aussieht** (keine Änderung nötig, gibt es seit V4.2):
`timetable` (class_subject_id + weekday `Mo`–`Fr` + start_time/end_time) + Datum = Zeile in `lessons`.
`attendance` hängt an `lessons.id` (`UNIQUE (student_id, lesson_id)`), nicht direkt an class_subject/date/start_time.
Die API rechnet `class_subject_id + date + start_time` selbst in die richtige Stunde um.
**Voraussetzung:** Das Fach muss an diesem Wochentag zu dieser Uhrzeit einen Eintrag im Stundenplan (`timetable`) haben.

| Methode + Pfad | Rolle | Antwort |
|---|---|---|
| `GET /attendance/slots?class_subject_id=1&date=2026-10-05` | Lehrkraft des Fachs, admin | Stunden laut Stundenplan an dem Tag: `[{timetable_id, weekday, start_time, end_time, room}]` (für die Auswahl von `start_time`) |
| `GET /attendance?class_subject_id=1&date=2026-10-05&start_time=08:00` | Lehrkraft des Fachs, admin | `LessonAttendanceOut` · `404` keine Stunde laut Stundenplan · `400` Wochenende |
| `PUT /attendance` | Lehrkraft des Fachs, admin | Body unten → `200 LessonAttendanceOut` (neuer Stand) |
| `GET /attendance/history?class_subject_id=1` | Lehrkraft des Fachs, admin | `[{lesson_id, date, start_time, end_time, present_count, absent_count, late_count}]`, neueste zuerst |

```json
// PUT /attendance
{ "class_subject_id": 1, "date": "2026-10-05", "start_time": "08:00",
  "entries": [ { "student_id": 3, "status": "abwesend" }, { "student_id": 9, "status": "anwesend" } ] }

// LessonAttendanceOut
{ "class_subject_id": 1, "date": "2026-10-05", "start_time": "08:00:00", "end_time": "08:50:00", "room": "A101",
  "lesson_id": 2, "cancelled": false,
  "students": [ { "student_id": 3, "first_name": "Test", "last_name": "Schueler", "username": "tschueler",
                  "status": "abwesend", "excuse_id": null, "enrolled": true } ] }
```

- `status` in `students`: `null` = noch nicht erfasst. `lesson_id: null` = für die Stunde gibt es noch gar nichts.
- Erlaubte Status: `anwesend`, `abwesend` und zusätzlich `verspaetet` (gibt es im Schema schon).
- Upsert: nur die mitgeschickten SchülerInnen werden angelegt/geändert, die anderen bleiben, wie sie sind.
- Wird jemand auf `anwesend` gesetzt, wird `excuse_id` auf `null` gesetzt (gilt auch für das alte `POST /attendance`).
- Fehler: `400` SchülerIn nicht im Fach / doppelt in der Liste / Datum in der Zukunft · `403` nicht mein Fach · `422` falscher Status oder leere Liste.
- Wer aus dem Fach ausgetragen wurde, aber für die Stunde schon einen Eintrag hat, kommt mit `"enrolled": false` mit.
- Testdaten: Mathe 4A (class_subject 1 lokal) hat Montag 08:00, erfasst am 05.10., 12.10., 19.10., 26.10. und 02.11.

## Username und Passwort ändern (V2.10)

| Methode + Pfad | Body | Antwort |
|---|---|---|
| `PATCH /users/me` | `{ "email": "..." }`, `{ "username": "..." }` oder beides | `200` UserOut · `409` E-Mail/Username vergeben · `422` ungültig oder leerer Body |
| `POST /users/me/password` | `{ "current_password": "...", "new_password": "..." }` | `204` · `400` aktuelles Passwort falsch · `422` neues Passwort unter 8 Zeichen · `429` zu viele Versuche (10/min) |

- Username: 3–50 Zeichen, Leerzeichen am Rand werden entfernt (wie bei Register).
- Der Login-Token bleibt nach einem Username-Wechsel gültig (er enthält die User-ID).
- Nach einer Passwortänderung bleiben schon ausgestellte Tokens bis zu ihrem Ablauf gültig (JWT kann man nicht einzeln sperren).
