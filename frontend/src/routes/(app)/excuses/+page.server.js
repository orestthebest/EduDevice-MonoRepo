import { error, fail } from '@sveltejs/kit';
import { excuseApi } from '$lib/server/excuses.js';
import { errorText } from '$lib/server/quiz.js';
import { api } from '$lib/server/api.js';

// Anhänge: gleiche Regeln wie in der API (V2.11)
const ATTACH_TYPES = ['application/pdf', 'image/jpeg', 'image/png'];
const ATTACH_MAX = 5 * 1024 * 1024;
const ATTACH_COUNT = 3;

// GET-Aufruf, wirft bei Fehlern direkt eine Fehlerseite
async function getJson(path, locals) {
	const res = await excuseApi(path, locals);
	if (!res.ok) error(res.status, await errorText(res, 'Could not load your excuses'));
	return res.json();
}

// Schülerseite: offene Fehlstunden + eigene Entschuldigungen
export async function load({ locals }) {
	if (locals.user.role !== 'schueler') error(403, 'Only students can submit excuses');

	const [absences, excuses] = await Promise.all([
		getJson('/attendance/me?unexcused=true', locals),
		getJson('/excuses/me', locals)
	]);
	return { absences, excuses };
}

export const actions = {
	// Entschuldigung für die ausgewählten Fehlstunden einreichen
	submit: async ({ request, locals }) => {
		const form = await request.formData();
		const reason = form.get('reason')?.toString().trim() ?? '';
		const ids = form.getAll('attendance_ids').map(Number);

		if (ids.length === 0) return fail(400, { reason, error: 'Please select at least one absence' });
		if (reason.length < 5) return fail(400, { reason, error: 'Please give a reason (at least 5 characters)' });
		if (reason.length > 1000) return fail(400, { reason, error: 'Reason is too long (max. 1000 characters)' });

		// Leere Einträge entfernen (Browser schickt ohne Auswahl eine leere Datei mit)
		const files = form.getAll('files').filter((f) => f instanceof File && f.size > 0);
		if (files.length > ATTACH_COUNT) {
			return fail(400, { reason, error: `You can attach max. ${ATTACH_COUNT} files` });
		}
		for (const f of files) {
			if (!ATTACH_TYPES.includes(f.type)) return fail(400, { reason, error: `${f.name}: only PDF, JPG or PNG allowed` });
			if (f.size > ATTACH_MAX) return fail(400, { reason, error: `${f.name} is too big (max. 5 MB)` });
		}

		const res = await excuseApi('/excuses', locals, {
			method: 'POST',
			json: { reason, attendance_ids: ids }
		});

		if (res.status === 400) {
			return fail(400, { reason, error: 'One of the selected lessons is already excused – please reload the page' });
		}

		if (!res.ok) return fail(res.status, { reason, error: await errorText(res, 'Could not submit your excuse') });

		// Entschuldigung ist angelegt -> jetzt die Dateien einzeln hochladen
		const excuse = await res.json();
		const failedFiles = [];
		for (const f of files) {
			const body = new FormData();
			body.append('file', f);
			const up = await api(`/excuses/${excuse.id}/attachments`, { method: 'POST', token: locals.token, form: body });
			if (!up.ok) failedFiles.push(f.name);
		}

		return { success: true, failedFiles };
	}
};