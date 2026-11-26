import { error, fail } from '@sveltejs/kit';
import { excuseApi } from '$lib/server/excuses.js';
import { errorText } from '$lib/server/quiz.js';
import { api } from '$lib/server/api.js';
import { m } from '$lib/paraglide/messages.js';

// Anhänge: gleiche Regeln wie in der API (V2.11)
const ATTACH_TYPES = ['application/pdf', 'image/jpeg', 'image/png'];
const ATTACH_MAX = 5 * 1024 * 1024;
const ATTACH_COUNT = 3;

// GET-Aufruf, wirft bei Fehlern direkt eine Fehlerseite
async function getJson(path, locals) {
	const res = await excuseApi(path, locals);
	if (!res.ok) error(res.status, await errorText(res, m.exc_err_load()));
	return res.json();
}

// Schülerseite: offene Fehlstunden + eigene Entschuldigungen
export async function load({ locals }) {
	if (locals.user.role !== 'schueler') error(403, m.exc_err_students_only());

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

		if (ids.length === 0) return fail(400, { reason, error: m.exc_err_select() });
		if (reason.length < 5) return fail(400, { reason, error: m.exc_err_reason_short() });
		if (reason.length > 1000) return fail(400, { reason, error: m.exc_err_reason_long() });

		// Leere Einträge entfernen (Browser schickt ohne Auswahl eine leere Datei mit)
		const files = form.getAll('files').filter((f) => f instanceof File && f.size > 0);
		if (files.length > ATTACH_COUNT) {
			return fail(400, { reason, error: m.exc_err_max_files({ n: ATTACH_COUNT }) });
		}
		for (const f of files) {
			if (!ATTACH_TYPES.includes(f.type)) return fail(400, { reason, error: m.exc_err_file_type_named({ name: f.name }) });
			if (f.size > ATTACH_MAX) return fail(400, { reason, error: m.exc_err_file_big_named({ name: f.name }) });
		}

		const res = await excuseApi('/excuses', locals, {
			method: 'POST',
			json: { reason, attendance_ids: ids }
		});

		if (res.status === 400) {
			return fail(400, { reason, error: m.exc_err_already_excused() });
		}

		if (!res.ok) return fail(res.status, { reason, error: await errorText(res, m.exc_err_submit()) });

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
	},

	// Anhang entfernen (nur eigene, nur solange pending – prüft die API)
	removeAttachment: async ({ request, locals }) => {
		const form = await request.formData();
		const id = Number(form.get('excuse_id'));
		const att = Number(form.get('attachment_id'));

		const res = await api(`/excuses/${id}/attachments/${att}`, { method: 'DELETE', token: locals.token });

		if (res.status === 409) return fail(409, { attachId: id, attachError: m.exc_err_reviewed() });
		if (!res.ok) return fail(res.status, { attachId: id, attachError: m.exc_err_remove_file() });
		return { attachId: id };
	},

	// Nachträglich eine Datei hinzufügen (z. B. Arztbestätigung kommt später)
	addAttachment: async ({ request, locals }) => {
		const form = await request.formData();
		const id = Number(form.get('excuse_id'));
		const file = form.get('file');

		if (!(file instanceof File) || file.size === 0) return fail(400, { attachId: id, attachError: m.subj_err_choose_file() });
		if (!ATTACH_TYPES.includes(file.type)) return fail(400, { attachId: id, attachError: m.exc_err_file_type() });
		if (file.size > ATTACH_MAX) return fail(400, { attachId: id, attachError: m.exc_err_file_big() });

		const body = new FormData();
		body.append('file', file);
		const res = await api(`/excuses/${id}/attachments`, { method: 'POST', token: locals.token, form: body });

		if (res.status === 409) return fail(409, { attachId: id, attachError: m.exc_err_max_or_reviewed() });
		if (res.status === 413) return fail(400, { attachId: id, attachError: m.exc_err_file_big() });
		if (res.status === 400) return fail(400, { attachId: id, attachError: m.exc_err_invalid_file() });
		if (!res.ok) return fail(res.status, { attachId: id, attachError: m.prof_err_upload() });
		return { attachId: id };
	}
};