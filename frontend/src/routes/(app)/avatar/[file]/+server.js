import { error } from '@sveltejs/kit';
import { api } from '$lib/server/api.js';
import { m } from '$lib/paraglide/messages.js';

// Profilbild: /avatar/12-1730123456.webp
// Das Bild liegt bei der REST-API, wir holen es mit dem Token und reichen es weiter.
// +server.js läuft NICHT durch das (app)-Layout, daher Login hier selbst prüfen
export async function GET({ params, locals }) {
	if (!locals.user) error(401, m.err_login());

	const res = await api(`/users/avatar/${encodeURIComponent(params.file)}`, { token: locals.token });
	if (!res.ok) error(res.status === 404 ? 404 : 502, m.av_err_not_found());

	return new Response(res.body, {
		headers: {
			'content-type': res.headers.get('content-type') ?? 'image/webp',
			// Dateiname enthält einen Zeitstempel -> neues Bild = neue URL, Caching ist sicher
			'cache-control': 'private, max-age=86400'
		}
	});
}