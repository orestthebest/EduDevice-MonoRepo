import { fail } from '@sveltejs/kit';
import {
	getSubjectsForUser,
	getClasses,
	getSubjectNames,
	createClassSubject
} from '$lib/server/subjects.js';

// Alle Fächer laden, die der eingeloggte User sehen darf
// (Lehrer bekommen zusätzlich Klassen + Fachnamen für den "New subject"-Dialog)
export async function load({ locals }) {
	const isTeacher = locals.user.role === 'lehrkraft';
	return {
		subjects: await getSubjectsForUser(locals.user),
		classes: isTeacher ? await getClasses() : [],
		subjectNames: isTeacher ? await getSubjectNames() : []
	};
}

export const actions = {
	// Neues Fach anlegen (nur Lehrer)
	create: async ({ request, locals }) => {
		// Rolle hier nochmal prüfen: Actions sind NICHT durch das Layout geschützt
		if (locals.user?.role !== 'lehrkraft') {
			return fail(403, { error: 'Only teachers can create subjects' });
		}

		const form = await request.formData();
		const classId = Number(form.get('class_id'));
		const name = form.get('name')?.toString().trim();

		if (!classId || !name) {
			return fail(400, { name, error: 'Please choose a class and enter a subject name' });
		}
		if (name.length > 150) {
			return fail(400, { name, error: 'Subject name is too long' });
		}

		try {
			await createClassSubject(locals.user.id, classId, name);
		} catch (err) {
			// UNIQUE (class_id, subject_id): Klasse hat dieses Fach schon
			if (err.code === 'ER_DUP_ENTRY') {
				return fail(400, { name, error: `This class already has the subject "${name}"` });
			}
			// Klasse existiert nicht (Foreign Key)
			if (err.code === 'ER_NO_REFERENCED_ROW_2') {
				return fail(400, { name, error: 'This class does not exist' });
			}
			throw err;
		}

		return { created: true };
	}
};