import { error } from '@sveltejs/kit';
import { api } from '$lib/server/api.js';
import { m } from '$lib/paraglide/messages.js';

// Download einer Datei: /materials/12
// Die Datei liegt bei der REST-API. Wir holen sie mit dem Token des Users
// und reichen sie direkt an den Browser weiter.
// +server.js läuft NICHT durch das (app)-Layout, daher Login hier selbst prüfen
export async function GET({ params, locals }) {
	if (!locals.user) error(401, m.err_login());

	const res = await api(`/materials/${Number(params.id)}/download`, { token: locals.token });

	if (res.status === 404) error(404, m.mat_err_not_found());
	if (!res.ok) error(res.status, m.mat_err_download());

	// Nur die wichtigen Header übernehmen: Dateityp, Größe, Originalname (Download statt Anzeigen)
	const headers = new Headers();
	for (const name of ['content-type', 'content-length', 'content-disposition']) {
		const value = res.headers.get(name);
		if (value) headers.set(name, value);
	}

	return new Response(res.body, { headers });
}