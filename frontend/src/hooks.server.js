import { sequence } from '@sveltejs/kit/hooks';
import { getTextDirection } from '$lib/paraglide/runtime.js';
import { paraglideMiddleware } from '$lib/paraglide/server.js';
import { api } from '$lib/server/api.js';

// Läuft bei jeder Anfrage: liest das Token (JWT) aus dem Cookie und fragt die
// REST-API, wer eingeloggt ist. Der User landet in event.locals.user.
async function originalHandle({ event, resolve }) {
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

/** @type {import('@sveltejs/kit').Handle} */ const handleParaglide = ({ event, resolve }) =>
	paraglideMiddleware(event.request, ({ request, locale }) => {
		return resolve(
			{ ...event, request },
			{
				transformPageChunk: ({ html }) =>
					html
						.replace('%paraglide.lang%', locale)
						.replace('%paraglide.dir%', getTextDirection(locale))
			}
		);
	});

export const handle = sequence(originalHandle, handleParaglide);
