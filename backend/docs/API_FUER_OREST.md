# EduDevice REST-API V2.3 – Anleitung für die WebApp

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
