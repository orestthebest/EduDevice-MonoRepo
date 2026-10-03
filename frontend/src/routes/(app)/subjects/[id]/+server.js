import { error } from '@sveltejs/kit';
import fs from 'node:fs/promises';
import { getMaterialForUser } from '$lib/server/subjects.js';
import { filePath } from '$lib/server/files.js';

// Download einer Datei: /materials/12
// +server.js läuft NICHT durch das (app)-Layout, daher Login hier selbst prüfen
export async function GET({ params, locals }) {
	if (!locals.user) error(401, 'Please log in');

	const material = await getMaterialForUser(Number(params.id), locals.user);
	if (!material) error(404, 'Material not found');

	let file;
	try {
		file = await fs.readFile(filePath(material.stored_name));
	} catch {
		error(404, 'File is missing on the server');
	}

	return new Response(file, {
		headers: {
			'Content-Type': material.mime_type,
			'Content-Length': String(file.length),
			// "attachment" = Browser lädt herunter; Originalname (auch mit Umlauten) wiederherstellen
			'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(material.original_name)}`
		}
	});
}