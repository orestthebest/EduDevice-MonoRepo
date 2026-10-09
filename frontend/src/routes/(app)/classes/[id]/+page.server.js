import { error, fail } from '@sveltejs/kit';
import {
	getClass,
	getClassStudents,
	getAssignableStudents,
	addStudentToClass,
	removeStudentFromClass
} from '$lib/server/classes.js';

// Klasse laden – nur Admins, sonst 403
async function loadClass(params, user) {
	if (user?.role !== 'admin') error(403, 'Only administrators can manage classes');
	const schoolClass = await getClass(Number(params.id));
	if (!schoolClass) error(404, 'Class not found');
	return schoolClass;
}

export async function load({ params, locals }) {
	const schoolClass = await loadClass(params, locals.user);
	return {
		schoolClass,
		students: await getClassStudents(schoolClass.id),
		assignableStudents: await getAssignableStudents(schoolClass.school_year_id)
	};
}

export const actions = {
	// Schüler der Klasse zuweisen (+ automatisch in alle Fächer der Klasse)
	addStudent: async ({ request, params, locals }) => {
		const schoolClass = await loadClass(params, locals.user);
		const form = await request.formData();
		const studentId = Number(form.get('student_id'));

		// Nur Schüler, die in diesem Schuljahr noch keine Klasse haben
		const assignable = await getAssignableStudents(schoolClass.school_year_id);
		if (!assignable.some((s) => s.id === studentId)) {
			return fail(400, { studentError: 'Student not found or already in a class this school year' });
		}

		await addStudentToClass(schoolClass.id, studentId);
		return { studentAdded: true };
	},

	// Schüler aus der Klasse entfernen (+ aus allen Fächern der Klasse)
	removeStudent: async ({ request, params, locals }) => {
		const schoolClass = await loadClass(params, locals.user);
		const form = await request.formData();
		await removeStudentFromClass(schoolClass.id, Number(form.get('student_id')));
		return { studentRemoved: true };
	}
};