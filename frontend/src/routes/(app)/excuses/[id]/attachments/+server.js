import { error } from '@sveltejs/kit';
import { api } from '$lib/server/api.js';

// Anhang einer Entschuldigung: /excuses/5/attachments/12
// Mit ?view öffnet der Browser die Datei (PDF/Bild) direkt, ohne ?view wird sie heruntergeladen.
// Wer sie sehen darf (SchülerIn selbst, Klassenvorstand, Admin), prüft die API.
// +server.js läuft NICHT durch das (app)-Layout, daher Login hier selbst prüfen
export async function GET({ params, locals, url }) {
	if (!locals.user) error(401, 'Please log in');

	const id = Number(params.id);
	const att = Number(params.att);
	if (!Number.isInteger(id) || !Number.isInteger(att)) error(404, 'Attachment not found');

	const res = await api(`/excuses/${id}/attachments/${att}/download`, { token: locals.token });

	if (res.status === 404) error(404, 'Attachment not found');
	if (!res.ok) error(res.status, 'Download failed');

	// Nur die wichtigen Header übernehmen: Dateityp, Größe, Originalname
	const headers = new Headers();
	for (const name of ['content-type', 'content-length', 'content-disposition']) {
		const value = res.headers.get(name);
		if (value) headers.set(name, value);
	}

	// ?view -> "inline" statt "attachment", damit PDF/Bild im Browser-Tab aufgeht
	const disposition = headers.get('content-disposition');
	if (url.searchParams.has('view') && disposition) {
		headers.set('content-disposition', disposition.replace(/^attachment/i, 'inline'));
	}
	headers.set('cache-control', 'private, no-store'); // Arztbestätigungen nicht im Cache lassen

	return new Response(res.body, { headers });
}