// frontend/src/lib/server/timetable.js
// Alle Stundenplan-Aufrufe laufen über diese Funktion.
//
// Solange Gridis Stundenplan-Endpunkte (Teil 3) noch nicht am Server laufen:
//   frontend/.env  ->  TIMETABLE_MOCK=1
// Dann antwortet der Mock (timetable-mock.js) mit denselben Formaten.
// Sobald die API fertig ist: Zeile aus der .env löschen – sonst ändert sich nichts.
import { env } from '$env/dynamic/private';
import { api } from './api.js';
import { mockApi } from './timetable-mock.js';

export function timetableApi(path, locals, { method = 'GET', json } = {}) {
	if (env.TIMETABLE_MOCK === '1') return mockApi(path, { method, json, user: locals.user });
	return api(path, { method, token: locals.token, json });
}