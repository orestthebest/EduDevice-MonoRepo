import { error, fail, redirect } from '@sveltejs/kit';
import { quizApi } from '$lib/server/quiz.js';

// Quiz lösen (nur Schüler). Schon abgegeben -> stattdessen das eigene Ergebnis zeigen.
// ?s=<Fach-ID> kommt von der Quiz-Liste und ist nur für den Zurück-Button.
export async function load({ params, locals, url }) {
	if (locals.user.role !== 'schueler') redirect(303, `/quizzes/${params.id}`);
	const back = url.searchParams.get('s') ? `/subjects/${Number(url.searchParams.get('s'))}/quizzes` : '/subjects';

	const res = await quizApi(`/quizzes/${params.id}/take`, locals);

	if (res.status === 409) {
		const resultRes = await quizApi(`/quizzes/${params.id}/my-result`, locals);
		if (!resultRes.ok) error(resultRes.status, 'Could not load your result');
		return { quiz: null, result: await resultRes.json(), back };
	}
	if (res.status === 404 || res.status === 403) error(404, 'Quiz not found');
	if (!res.ok) error(res.status, 'Could not load the quiz');

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
			let m;
			if ((m = key.match(/^opt_(\d+)$/))) {
				const a = answerFor(Number(m[1]));
				(a.option_ids ??= []).push(Number(value));
			} else if ((m = key.match(/^gap_(\d+)_(\d+)$/))) {
				const a = answerFor(Number(m[1]));
				(a.gaps ??= [])[Number(m[2])] = value.toString();
			}
		}
		// Lücken ohne Eingabe als leeren Text schicken (keine Löcher im Array)
		for (const a of answers.values()) if (a.gaps) a.gaps = Array.from(a.gaps, (g) => g ?? '');

		const res = await quizApi(`/quizzes/${params.id}/submit`, locals, {
			method: 'POST',
			json: { answers: [...answers.values()] }
		});

		if (res.status === 409) return fail(409, { error: 'You have already submitted this quiz.' });
		if (res.status === 404) return fail(404, { error: 'This quiz is no longer available.' });
		if (!res.ok) return fail(res.status, { error: 'Could not submit, please try again.' });

		return { result: await res.json() };
	}
};