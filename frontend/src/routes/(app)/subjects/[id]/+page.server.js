import { error, fail } from '@sveltejs/kit';
import { getClassSubjectForUser, getMaterials, insertMaterial, getSubjectStudents, getAddableStudents, addStudent, removeStudent } from '$lib/server/subjects.js';
import { saveFile, deleteFile, getExtension, ALLOWED_EXTENSIONS, MAX_SIZE } from '$lib/server/files.js';

// Fach + Materialien laden. Kein Zugriff -> 404 (wir verraten nicht, dass es das Fach gibt)
export async function load({ params, locals }) {
	const subject = await getClassSubjectForUser(Number(params.id), locals.user);
	if (!subject) error(404, 'Subject not found');

	// Schülerliste nur für den Lehrer des Fachs laden
	const isOwner = locals.user.role === 'lehrkraft' && subject.teacher_id === locals.user.id;

	return {
		subject,
		materials: await getMaterials(subject.id),
		students: isOwner ? await getSubjectStudents(subject.id) : [],
		addableStudents: isOwner ? await getAddableStudents(subject.id) : [],
		allowedExtensions: ALLOWED_EXTENSIONS,
		maxSizeMb: MAX_SIZE / 1024 / 1024
	};
}

// Prüft, ob der User Lehrer DIESES Fachs ist (für alle Aktionen)
async function getOwnSubject(params, user) {
	if (user?.role !== 'lehrkraft') return null;
	const subject = await getClassSubjectForUser(Number(params.id), user);
	return subject && subject.teacher_id === user.id ? subject : null;
}

export const actions = {
	// Material hochladen (nur der Lehrer des Fachs)
	upload: async ({ request, params, locals }) => {
		const subject = await getOwnSubject(params, locals.user);
		if (!subject) return fail(403, { error: 'You are not allowed to upload here' });

		const form = await request.formData();
		const file = form.get('file');
		const title = form.get('title')?.toString().trim();

		// Datei prüfen: vorhanden, Typ erlaubt, nicht zu groß
		if (!(file instanceof File) || file.size === 0) {
			return fail(400, { title, error: 'Please choose a file' });
		}
		if (!ALLOWED_EXTENSIONS.includes(getExtension(file.name))) {
			return fail(400, { title, error: 'This file type is not allowed' });
		}
		if (file.size > MAX_SIZE) {
			return fail(400, { title, error: `File is too big (max. ${MAX_SIZE / 1024 / 1024} MB)` });
		}
		if (!title || title.length > 150) {
			return fail(400, { title, error: 'Please enter a title (max. 150 characters)' });
		}

		// 1. Datei in den uploads-Ordner schreiben, 2. Eintrag in der DB
		const storedName = await saveFile(file);
		try {
			await insertMaterial({
				classSubjectId: subject.id,
				uploadedBy: locals.user.id,
				title,
				originalName: file.name,
				storedName,
				mimeType: file.type || 'application/octet-stream',
				sizeBytes: file.size
			});
		} catch (err) {
			// DB-Fehler: Datei wieder löschen, damit keine "Leichen" im Ordner bleiben
			await deleteFile(storedName);
			throw err;
		}

				return { uploaded: true };
	},

	// Schüler zum Fach hinzufügen (nur der Lehrer des Fachs)
	addStudent: async ({ request, params, locals }) => {
		const subject = await getOwnSubject(params, locals.user);
		if (!subject) return fail(403, { studentError: 'You are not allowed to do this' });

		const form = await request.formData();
		const studentId = Number(form.get('student_id'));
		if (!studentId) return fail(400, { studentError: 'Please choose a student' });

		const added = await addStudent(subject.id, studentId);
		if (!added) return fail(400, { studentError: 'Student not found or already added' });

		return { studentAdded: true };
	},

	// Schüler aus dem Fach entfernen (nur der Lehrer des Fachs)
	removeStudent: async ({ request, params, locals }) => {
		const subject = await getOwnSubject(params, locals.user);
		if (!subject) return fail(403, { studentError: 'You are not allowed to do this' });

		const form = await request.formData();
		await removeStudent(subject.id, Number(form.get('student_id')));

		return { studentRemoved: true };
	}
};