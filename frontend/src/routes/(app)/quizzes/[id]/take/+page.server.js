import { error, fail, redirect } from '@sveltejs/kit';
import { quizApi } from '$lib/server/quiz.js';
import { m } from '$lib/paraglide/messages.js';

// Quiz lösen (nur Schüler). Schon abgegeben -> stattdessen das eigene Ergebnis zeigen.
// ?s=<Fach-ID> kommt von der Quiz-Liste und ist nur für den Zurück-Button.
export async function load({ params, locals, url }) {
	if (locals.user.role !== 'schueler') redirect(303, `/quizzes/${params.id}`);
	const back = url.searchParams.get('s') ? `/subjects/${Number(url.searchParams.get('s'))}/quizzes` : '/subjects';

	const res = await quizApi(`/quizzes/${params.id}/take`, locals);

	if (res.status === 409) {
		const resultRes = await quizApi(`/quizzes/${params.id}/my-result`, locals);
		if (!resultRes.ok) error(resultRes.status, m.quiz_err_load_result());
		return { quiz: null, result: await resultRes.json(), back };
	}
	if (res.status === 404 || res.status === 403) error(404, m.quiz_err_not_found());
	if (!res.ok) error(res.status, m.quiz_err_load());

	return { quiz: await res.json(), result: null, back };
}

export const actions = {
	// Formularfelder -> Body von POST /quizzes/{id}/submit
	//   opt_<frage-id>        = gewählte Option(en) bei Multiple Choice und Wahr/Falsch
	//   gap_<frage-id>_<nr>   = Text in Lücke <nr>
	// Die API bewertet – die WebApp schickt nur die Antworten.
	submit: async ({ request, params, locals }) => {
		const form = await request.formData();
		const answers = new Map();
		const answerFor = (questionId) => {
			if (!answers.has(questionId)) answers.set(questionId, { question_id: questionId });
			return answers.get(questionId);
		};

		for (const [key, value] of form.entries()) {
			let match;
			if ((match = key.match(/^opt_(\d+)$/))) {
				const a = answerFor(Number(match[1]));
				(a.option_ids ??= []).push(Number(value));
			} else if ((match = key.match(/^gap_(\d+)_(\d+)$/))) {
				const a = answerFor(Number(match[1]));
				(a.gaps ??= [])[Number(match[2])] = value.toString();
			}
		}
		// Lücken ohne Eingabe als leeren Text schicken (keine Löcher im Array)
		for (const a of answers.values()) if (a.gaps) a.gaps = Array.from(a.gaps, (g) => g ?? '');

		const res = await quizApi(`/quizzes/${params.id}/submit`, locals, {
			method: 'POST',
			json: { answers: [...answers.values()] }
		});

		if (res.status === 409) return fail(409, { error: m.quiz_err_already() });
		if (res.status === 404) return fail(404, { error: m.quiz_err_unavailable() });
		if (!res.ok) return fail(res.status, { error: m.quiz_err_submit() });

		return { result: await res.json() };
	}
};