import { error, fail } from '@sveltejs/kit';
import { api, apiJson } from '$lib/server/api.js';
import { timetableApi } from '$lib/server/timetable.js';
import { errorText } from '$lib/server/quiz.js';
import { SPLIT_GROUPS, isElective } from '$lib/groups.js';
import { m } from '$lib/paraglide/messages.js';

// Eine Klasse mit ihren Schülern – nur für Admins
export async function load({ params, locals }) {
	if (locals.user.role !== 'admin') error(403, m.cls_err_admins_only());

	const token = locals.token;
	const base = `/classes/${params.id}`;

	// apiJson zeigt bei 404 automatisch die Fehlerseite ("Klasse nicht gefunden")
	const [schoolClass, students, assignableStudents, teachers, groupsRes] = await Promise.all([
		apiJson(base, { token }),
		apiJson(`${base}/students`, { token }),
		apiJson(`${base}/assignable-students`, { token }),
		apiJson('/users?role=lehrkraft', { token }), // für die Klassenvorstand-Auswahl
		timetableApi(`${base}/groups`, locals) // Gruppe X/Y + Wahlfach pro SchülerIn (Mock möglich)
	]);

	// null = die API kann noch keine Gruppen -> die Seite blendet die Spalten aus
	const groups = groupsRes.ok ? await groupsRes.json() : null;

	return { schoolClass, students, assignableStudents, teachers, groups };
}

export const actions = {
	// Schüler der Klasse zuweisen (die API trägt ihn auch in alle Fächer der Klasse ein)
	addStudent: async ({ request, params, locals }) => {
		const form = await request.formData();
		const res = await api(`/classes/${params.id}/students`, {
			method: 'POST',
			token: locals.token,
			json: { student_id: Number(form.get('student_id')) }
		});

		if (!res.ok) {
			return fail(res.status, { studentError: m.cls_err_add() });
		}
		return { studentAdded: true };
	},

	// Schüler aus der Klasse entfernen (die API entfernt ihn auch aus allen Fächern der Klasse)
	removeStudent: async ({ request, params, locals }) => {
		const form = await request.formData();
		const res = await api(`/classes/${params.id}/students/${Number(form.get('student_id'))}`, {
			method: 'DELETE',
			token: locals.token
		});

		if (!res.ok) {
			return fail(res.status, { studentError: m.subj_err_student_remove() });
		}
		return { studentRemoved: true };
	},

	// Klassenvorstand setzen oder entfernen ("" = keiner)
	setClassTeacher: async ({ request, params, locals }) => {
		const form = await request.formData();
		const value = form.get('class_teacher_id')?.toString() ?? '';

		const res = await api(`/classes/${params.id}`, {
			method: 'PATCH',
			token: locals.token,
			json: { class_teacher_id: value ? Number(value) : null }
		});

		if (res.status === 400) return fail(400, { teacherError: m.cls_err_only_teachers() });
		if (!res.ok) return fail(res.status, { teacherError: m.cls_err_save_teacher() });
		return { teacherSaved: true };
	},

	// Gruppe (X/Y) + Wahlfach aller SchülerInnen auf einmal speichern.
	// Formular: group_<id> und elective_<id> pro SchülerIn ("" = keine)
	saveGroups: async ({ request, params, locals }) => {
		const form = await request.formData();
		const assignments = [];

		for (const [key, value] of form) {
			const match = key.match(/^group_(\d+)$/);
			if (!match) continue;
			const studentId = Number(match[1]);
			const group = value.toString() || null;
			const elective = form.get(`elective_${studentId}`)?.toString() || null;

			if (group && !SPLIT_GROUPS.includes(group)) return fail(400, { groupError: m.cls_err_groups() });
			if (elective && !isElective(elective)) return fail(400, { groupError: m.cls_err_groups() });
			assignments.push({ student_id: studentId, group, elective });
		}

		// Die API trägt die SchülerInnen danach automatisch in die passenden Gruppen-/Wahlfach-Fächer ein
		const res = await timetableApi(`/classes/${params.id}/groups`, locals, { method: 'PUT', json: { assignments } });
		if (!res.ok) return fail(res.status, { groupError: await errorText(res, m.cls_err_groups()) });
		return { groupsSaved: true };
	}
};