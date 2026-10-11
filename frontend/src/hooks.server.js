import { api } from '$lib/server/api.js';

// Läuft bei jeder Anfrage: liest das Token (JWT) aus dem Cookie und fragt die
// REST-API, wer eingeloggt ist. Der User landet in event.locals.user.
export async function handle({ event, resolve }) {
	const token = event.cookies.get('token');
	event.locals.token = token ?? null;
	event.locals.user = null;

	if (token) {
		const res = await api('/auth/me', { token });
		if (res.ok) {
			event.locals.user = await res.json();
		} else {
			// Token abgelaufen (nach 60 Min.) oder ungültig -> Cookie löschen = ausgeloggt
			event.locals.token = null;
			event.cookies.delete('token', { path: '/', secure: event.url.protocol === 'https:' });
		}
	}

	return resolve(event);
}