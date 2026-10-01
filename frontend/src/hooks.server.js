import { validateSession } from '$lib/server/auth.js';

// Läuft bei jeder Anfrage: liest die Session aus dem Cookie und legt den
// eingeloggten User in event.locals ab, damit ihn alle Seiten nutzen können.
export async function handle({ event, resolve }) {
	const sessionId = event.cookies.get('session');
	event.locals.user = sessionId ? await validateSession(sessionId) : null;
	return resolve(event);
}