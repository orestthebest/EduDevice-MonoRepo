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


// "09:35:00" -> "3rd period" (liegt die Zeit nicht im Raster: einfach die Uhrzeit)
export function periodLabel(time) {
	const p = periodOf(time);
	if (!p) return String(time).slice(0, 5);
	const suffix = p === 1 ? 'st' : p === 2 ? 'nd' : p === 3 ? 'rd' : 'th';
	return `${p}${suffix} period`;
}