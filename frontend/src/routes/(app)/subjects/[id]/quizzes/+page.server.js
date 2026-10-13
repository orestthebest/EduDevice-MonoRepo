import { error, fail, redirect } from '@sveltejs/kit';
import { api } from '$lib/server/api.js';
import { quizApi, errorText } from '$lib/server/quiz.js';

// Quiz-Liste eines Fachs: Lehrkraft sieht alle (inkl. Entwürfe), Schüler nur veröffentlichte
export async function load({ params, locals }) {
	const res = await api(`/subjects/${params.id}`, { token: locals.token });
	if (res.status === 404) error(404, 'Subject not found');
	if (!res.ok) error(res.status, 'Could not load the subject');
	const subject = await res.json();

	const { role, id } = locals.user;
	const isOwner = role === 'lehrkraft' && subject.teacher_id === id;
	if (!isOwner && role !== 'schueler') error(403, 'Only the teacher and the students of this subject can open quizzes');

	const quizRes = await quizApi(`/subjects/${params.id}/quizzes`, locals);
	if (!quizRes.ok) error(quizRes.status, 'Could not load the quizzes');

	return { subject, isOwner, quizzes: await quizRes.json() };
}

export const actions = {
	// Neues Quiz anlegen -> danach direkt in den Editor
	create: async ({ request, params, locals }) => {
		const form = await request.formData();
		const title = form.get('title')?.toString().trim() ?? '';
		const description = form.get('description')?.toString().trim() ?? '';

		if (!title || title.length > 150) {
			return fail(400, { title, description, error: 'Please enter a title (max. 150 characters)' });
		}

		const res = await quizApi(`/subjects/${params.id}/quizzes`, locals, {
			method: 'POST',
			json: { title, description: description || null }
		});
		if (!res.ok) {
			return fail(res.status, { title, description, error: await errorText(res, 'Could not create the quiz') });
		}

		const quiz = await res.json();
		redirect(303, `/quizzes/${quiz.id}`);
	}
};