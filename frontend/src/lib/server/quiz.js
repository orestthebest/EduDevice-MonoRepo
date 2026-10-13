// frontend/src/lib/server/quiz.js
// Alle Quiz-Aufrufe laufen über diese Funktion (Vertrag: backend/docs/QUIZ_API.md).
//
// Solange Gridis Quiz-Endpunkte noch nicht am Server laufen:
//   frontend/.env  ->  QUIZ_MOCK=1
// Dann antwortet der Mock (quiz-mock.js) mit genau denselben Formaten.
// Sobald die API fertig ist: Zeile aus der .env löschen – sonst ändert sich nichts.
import { env } from '$env/dynamic/private';
import { api } from './api.js';
import { mockApi } from './quiz-mock.js';

export function quizApi(path, locals, { method = 'GET', json } = {}) {
	if (env.QUIZ_MOCK === '1') return mockApi(path, { method, json, user: locals.user });
	return api(path, { method, token: locals.token, json });
}

// Fehlertext aus der API-Antwort {"detail": "..."} holen (sonst fallback)
export async function errorText(res, fallback) {
	try {
		const data = await res.json();
		if (typeof data.detail === 'string') return data.detail;
	} catch {
		/* keine JSON-Antwort */
	}
	return fallback;
}