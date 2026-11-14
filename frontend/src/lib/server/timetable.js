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

// mock = Zusatzinfos nur für den Mock (z. B. Klasse/Lehrkraft) – an die echte API geht das nie
export function timetableApi(path, locals, { method = 'GET', json, mock } = {}) {
	if (env.TIMETABLE_MOCK === '1') return mockApi(path, { method, json, user: locals.user, extra: mock });
	return api(path, { method, token: locals.token, json });
}