// frontend/src/lib/server/excuses.js
// Alle Entschuldigungs-Aufrufe laufen über diese Funktion (Vertrag: backend/docs/API_FUER_OREST.md).
import { api } from './api.js';

export function excuseApi(path, locals, { method = 'GET', json } = {}) {
	return api(path, { method, token: locals.token, json });
}