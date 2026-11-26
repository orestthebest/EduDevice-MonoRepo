import { fail } from '@sveltejs/kit';
import { api, apiJson } from '$lib/server/api.js';
import { m } from '$lib/paraglide/messages.js';

// Alle Fächer laden, die der User sehen darf (die API filtert nach Rolle)
// Lehrer bekommen zusätzlich Klassen + Fachnamen für den "New subject"-Dialog
export async function load({ locals }) {
	const token = locals.token;
	const isTeacher = locals.user.role === 'lehrkraft';

	const [subjects, classes, subjectNames] = await Promise.all([
		apiJson('/subjects', { token }),
		isTeacher ? apiJson('/classes', { token }) : [],
		isTeacher ? apiJson('/subjects/names', { token }) : []
	]);

	return { subjects, classes, subjectNames };
}

export const actions = {
	// Neues Fach anlegen (nur Lehrer – das prüft die API)
	create: async ({ request, locals }) => {
		const form = await request.formData();
		const classId = Number(form.get('class_id'));
		const name = form.get('name')?.toString().trim();

		if (!classId || !name) {
			return fail(400, { name, error: m.subj_err_fill() });
		}
		if (name.length > 150) {
			return fail(400, { name, error: m.subj_err_name_long() });
		}

		const res = await api('/subjects', {
			method: 'POST',
			token: locals.token,
			json: { class_id: classId, name }
		});

		if (res.status === 409) {
			return fail(400, { name, error: m.subj_err_exists({ name }) });
		}
		if (res.status === 403) {
			return fail(403, { name, error: m.subj_err_only_teachers() });
		}
		if (!res.ok) {
			return fail(400, { name, error: m.subj_err_no_class() });
		}

		return { created: true };
	}
};