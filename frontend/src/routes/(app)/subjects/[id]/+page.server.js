import { error, fail, redirect } from '@sveltejs/kit';
import { api, apiJson } from '$lib/server/api.js';
import { m } from '$lib/paraglide/messages.js';

// Fach + Materialien laden. Kein Zugriff -> API antwortet 404
export async function load({ params, locals }) {
	const token = locals.token;
	const base = `/subjects/${params.id}`;

	const res = await api(base, { token });
	if (res.status === 404) error(404, m.subj_err_not_found());
	if (!res.ok) error(res.status, m.subj_err_load());
	const subject = await res.json();

	// Schülerliste + Upload nur für den Lehrer des Fachs
	const isOwner = locals.user.role === 'lehrkraft' && subject.teacher_id === locals.user.id;

	const [materials, students, addableStudents, config] = await Promise.all([
		apiJson(`${base}/materials`, { token }),
		isOwner ? apiJson(`${base}/students`, { token }) : [],
		isOwner ? apiJson(`${base}/addable-students`, { token }) : [],
		apiJson('/materials/config', { token })
	]);

	return {
		subject,
		materials,
		students,
		addableStudents,
		allowedExtensions: config.allowed_extensions,
		maxSizeMb: config.max_size_mb
	};
}

export const actions = {
	// Material hochladen: Formular (file + title) wird direkt an die API weitergereicht.
	// Die API prüft Berechtigung, Dateityp, Größe und speichert die Datei.
	upload: async ({ request, params, locals }) => {
		const form = await request.formData();
		const file = form.get('file');
		const title = form.get('title')?.toString().trim();

		if (!(file instanceof File) || file.size === 0) {
			return fail(400, { title, error: m.subj_err_choose_file() });
		}
		if (!title || title.length > 150) {
			return fail(400, { title, error: m.subj_err_title() });
		}

		const res = await api(`/subjects/${params.id}/materials`, {
			method: 'POST',
			token: locals.token,
			form
		});

		if (res.status === 413) return fail(400, { title, error: m.subj_err_file_big() });
		if (res.status === 400) return fail(400, { title, error: m.subj_err_file_type()});
		if (res.status === 403) return fail(403, { title, error: m.subj_err_upload_forbidden()});
		if (!res.ok) return fail(res.status, { title, error: m.prof_err_upload() });

		return { uploaded: true };
	},

	// Schüler zum Fach hinzufügen (nur Schüler der Klasse des Fachs – prüft die API)
	addStudent: async ({ request, params, locals }) => {
		const form = await request.formData();
		const studentId = Number(form.get('student_id'));
		if (!studentId) return fail(400, { studentError: m.subj_err_choose_student() });

		const res = await api(`/subjects/${params.id}/students`, {
			method: 'POST',
			token: locals.token,
			json: { student_id: studentId }
		});

		if (!res.ok) return fail(res.status, { studentError: m.subj_err_student_add() });
		return { studentAdded: true };
	},

	// Schüler aus dem Fach entfernen
	removeStudent: async ({ request, params, locals }) => {
		const form = await request.formData();
		const res = await api(`/subjects/${params.id}/students/${Number(form.get('student_id'))}`, {
			method: 'DELETE',
			token: locals.token
		});

		if (!res.ok) return fail(res.status, { studentError: m.subj_err_student_remove() });
		return { studentRemoved: true };
	},

	// Material löschen (DB-Eintrag + Datei löscht die API)
	deleteMaterial: async ({ request, params, locals }) => {
		const form = await request.formData();
		const res = await api(`/subjects/${params.id}/materials/${Number(form.get('material_id'))}`, {
			method: 'DELETE',
			token: locals.token
		});

		if (res.status === 404) return fail(404, { deleteError: m.mat_err_not_found() });
		if (!res.ok) return fail(res.status, { deleteError: m.err_forbidden() });
		return { deleted: true };
	},

	// Ganzes Fach löschen, danach zurück zur Übersicht
	deleteSubject: async ({ params, locals }) => {
		const res = await api(`/subjects/${params.id}`, {
			method: 'DELETE',
			token: locals.token
		});

		if (res.status === 409) {
			return fail(409, {
				deleteError: m.subj_err_has_data()
			});
		}
		if (!res.ok) return fail(res.status, { deleteError: m.err_forbidden() });

		redirect(303, '/subjects');
	}
};