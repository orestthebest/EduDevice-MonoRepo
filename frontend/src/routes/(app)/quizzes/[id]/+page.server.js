import { error, fail, redirect } from '@sveltejs/kit';
import { quizApi, errorText } from '$lib/server/quiz.js';
import { m } from '$lib/paraglide/messages.js';

// Quiz-Editor + Ergebnisse (nur Lehrkraft). Schüler landen auf der Seite zum Lösen.
export async function load({ params, locals }) {
	if (locals.user.role === 'schueler') redirect(303, `/quizzes/${params.id}/take`);

	const res = await quizApi(`/quizzes/${params.id}`, locals);
	if (res.status === 404 || res.status === 403) error(404, m.quiz_err_not_found());
	if (!res.ok) error(res.status, m.quiz_err_load());
	const quiz = await res.json();

	const attemptsRes = await quizApi(`/quizzes/${params.id}/attempts`, locals);
	if (!attemptsRes.ok) error(attemptsRes.status, m.quiz_err_load_results());

	return { quiz, attempts: await attemptsRes.json() };
}

// Gemeinsame Fehlerbehandlung für alle Aktionen
async function failed(res) {
	if (res.status === 409) return fail(409, { error: m.quiz_err_locked() });
	if (res.status === 404) return fail(404, { error: m.err_not_found_reload() });
	return fail(res.status, { error: await errorText(res, m.err_generic()) });
}

export const actions = {
	// Titel + Beschreibung ändern
	details: async ({ request, params, locals }) => {
		const form = await request.formData();
		const title = form.get('title')?.toString().trim() ?? '';
		const description = form.get('description')?.toString().trim() ?? '';
		if (!title || title.length > 150) return fail(400, { error: m.subj_err_title() });

		const res = await quizApi(`/quizzes/${params.id}`, locals, {
			method: 'PUT',
			json: { title, description: description || null }
		});
		if (!res.ok) return failed(res);
		return { saved: m.quiz_details_saved() };
	},

	// Veröffentlichen / wieder ausblenden (geht auch, wenn das Quiz gesperrt ist)
	publish: async ({ request, params, locals }) => {
		const form = await request.formData();
		const publish = form.get('publish') === 'true';

		const res = await quizApi(`/quizzes/${params.id}`, locals, { method: 'PUT', json: { is_published: publish } });
		if (!res.ok) return failed(res);
		return { saved: publish ? m.quiz_published_msg() : m.quiz_hidden_msg() };
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
			return fail(400, { error: m.quiz_err_invalid() });
		}

		const res = questionId
			? await quizApi(`/questions/${questionId}`, locals, { method: 'PUT', json: body })
			: await quizApi(`/quizzes/${params.id}/questions`, locals, { method: 'POST', json: body });
		if (!res.ok) return failed(res);
		return { saved: questionId ? m.quiz_q_updated() : m.quiz_q_added() };
	},

	deleteQuestion: async ({ request, locals }) => {
		const form = await request.formData();
		const res = await quizApi(`/questions/${Number(form.get('question_id'))}`, locals, { method: 'DELETE' });
		if (!res.ok) return failed(res);
		return { saved: m.quiz_q_deleted() };
	}
};