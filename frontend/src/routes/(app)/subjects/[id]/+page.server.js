import { error } from '@sveltejs/kit';
import { getClassSubjectForUser, getMaterials } from '$lib/server/subjects.js';

// Fach + Materialien laden. Kein Zugriff -> 404 (wir verraten nicht, dass es das Fach gibt)
export async function load({ params, locals }) {
	const subject = await getClassSubjectForUser(Number(params.id), locals.user);
	if (!subject) error(404, 'Subject not found');

	return {
		subject,
		materials: await getMaterials(subject.id)
	};
}