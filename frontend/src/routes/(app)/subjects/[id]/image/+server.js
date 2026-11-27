import { error } from '@sveltejs/kit';
import { api } from '$lib/server/api.js';
import { m } from '$lib/paraglide/messages.js';

// Fachbild: /subjects/5/image?v=<dateiname>
// Das Bild liegt bei der REST-API, wir holen es mit dem Token und reichen es weiter (wie /avatar/[file]).
// +server.js läuft NICHT durch das (app)-Layout, daher Login hier selbst prüfen
export async function GET({ params, locals }) {
	if (!locals.user) error(401, m.err_login());

	const id = Number(params.id);
	if (!Number.isInteger(id)) error(404, m.av_err_not_found());

	const res = await api(`/subjects/${id}/image`, { token: locals.token });
	if (!res.ok) error(res.status === 404 ? 404 : 502, m.av_err_not_found());

	return new Response(res.body, {
		headers: {
			'content-type': res.headers.get('content-type') ?? 'image/webp',
			// ?v= wechselt bei jedem neuen Bild -> lange Caching-Zeit ist sicher
			'cache-control': 'private, max-age=86400'
		}
	});
}