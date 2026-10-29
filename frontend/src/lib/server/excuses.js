// frontend/src/lib/server/excuses.js
// Alle Entschuldigungs-Aufrufe laufen über diese Funktion.
//
// Solange Gridis Endpunkte noch nicht am Server laufen:
//   frontend/.env  ->  EXCUSE_MOCK=1
// Sobald die API fertig ist: Zeile aus der .env löschen.
import { env } from '$env/dynamic/private';
import { api } from './api.js';
import { mockApi } from './excuse-mock.js';

export function excuseApi(path, locals, { method = 'GET', json } = {}) {
	if (env.EXCUSE_MOCK === '1') return mockApi(path, { method, json, user: locals.user });
	return api(path, { method, token: locals.token, json });
}