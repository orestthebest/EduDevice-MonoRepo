import { error, fail, redirect } from '@sveltejs/kit';
import { quizApi, errorText } from '$lib/server/quiz.js';

// Quiz-Editor + Ergebnisse (nur Lehrkraft). Schüler landen auf der Seite zum Lösen.
export async function load({ params, locals }) {
	if (locals.user.role === 'schueler') redirect(303, `/quizzes/${params.id}/take`);

	const res = await quizApi(`/quizzes/${params.id}`, locals);
	if (res.status === 404 || res.status === 403) error(404, 'Quiz not found');
	if (!res.ok) error(res.status, 'Could not load the quiz');
	const quiz = await res.json();

	const attemptsRes = await quizApi(`/quizzes/${params.id}/attempts`, locals);
	if (!attemptsRes.ok) error(attemptsRes.status, 'Could not load the results');

	return { quiz, attempts: await attemptsRes.json() };
}

// Gemeinsame Fehlerbehandlung für alle Aktionen
async function failed(res) {
	if (res.status === 409) return fail(409, { error: 'Students have already submitted this quiz, so it can no longer be changed.' });
	if (res.status === 404) return fail(404, { error: 'Not found. Please reload the page.' });
	return fail(res.status, { error: await errorText(res, 'Something went wrong, please try again.') });
}

export const actions = {
	// Titel + Beschreibung ändern
	details: async ({ request, params, locals }) => {
		const form = await request.formData();
		const title = form.get('title')?.toString().trim() ?? '';
		const description = form.get('description')?.toString().trim() ?? '';
		if (!title || title.length > 150) return fail(400, { error: 'Please enter a title (max. 150 characters)' });

		const res = await quizApi(`/quizzes/${params.id}`, locals, {
			method: 'PUT',
			json: { title, description: description || null }
		});
		if (!res.ok) return failed(res);
		return { saved: 'Details saved.' };
	},

	// Veröffentlichen / wieder ausblenden (geht auch, wenn das Quiz gesperrt ist)
	publish: async ({ request, params, locals }) => {
		const form = await request.formData();
		const publish = form.get('publish') === 'true';

		const res = await quizApi(`/quizzes/${params.id}`, locals, { method: 'PUT', json: { is_published: publish } });
		if (!res.ok) return failed(res);
		return { saved: publish ? 'Quiz published. Students can now take it.' : 'Quiz hidden from students.' };
	},

	// Ganzes Quiz löschen, danach zurück zur Liste des Fachs
	deleteQuiz: async ({ request, params, locals }) => {
		const form = await request.formData();
		const res = await quizApi(`/quizzes/${params.id}`, locals, { method: 'DELETE' });
		if (!res.ok) return failed(res);
		redirect(303, `/subjects/${Number(form.get('class_subject_id'))}/quizzes`);
	},

	// Frage anlegen (ohne question_id) oder ersetzen (mit question_id).
	// Der Body kommt fertig als JSON vom Formular (QuestionForm.svelte) – die API prüft ihn.
	saveQuestion: async ({ request, params, locals }) => {
		const form = await request.formData();
		const questionId = Number(form.get('question_id')) || null;

		let body;
		try {
			body = JSON.parse(form.get('payload')?.toString() ?? '');
		} catch {
			return fail(400, { error: 'Invalid question data' });
		}

		const res = questionId
			? await quizApi(`/questions/${questionId}`, locals, { method: 'PUT', json: body })
			: await quizApi(`/quizzes/${params.id}/questions`, locals, { method: 'POST', json: body });
		if (!res.ok) return failed(res);
		return { saved: questionId ? 'Question updated.' : 'Question added.' };
	},

	deleteQuestion: async ({ request, locals }) => {
		const form = await request.formData();
		const res = await quizApi(`/questions/${Number(form.get('question_id'))}`, locals, { method: 'DELETE' });
		if (!res.ok) return failed(res);
		return { saved: 'Question deleted.' };
	}
};