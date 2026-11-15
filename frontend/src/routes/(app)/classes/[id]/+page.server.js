import { error, fail } from '@sveltejs/kit';
import { api, apiJson } from '$lib/server/api.js';

// Eine Klasse mit ihren Schülern – nur für Admins
export async function load({ params, locals }) {
	if (locals.user.role !== 'admin') error(403, 'Only administrators can manage classes');

	const token = locals.token;
	const base = `/classes/${params.id}`;

	// apiJson zeigt bei 404 automatisch die Fehlerseite ("Klasse nicht gefunden")
	const [schoolClass, students, assignableStudents, teachers] = await Promise.all([
		apiJson(base, { token }),
		apiJson(`${base}/students`, { token }),
		apiJson(`${base}/assignable-students`, { token }),
		apiJson('/users?role=lehrkraft', { token }) // für die Klassenvorstand-Auswahl
	]);

	return { schoolClass, students, assignableStudents, teachers };
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
			return fail(res.status, { studentError: 'Student not found or already in a class this school year' });
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
			return fail(res.status, { studentError: 'Could not remove the student' });
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

		if (res.status === 400) return fail(400, { teacherError: 'Only teachers can be class teachers' });
		if (!res.ok) return fail(res.status, { teacherError: 'Could not save the class teacher' });
		return { teacherSaved: true };
	}
};