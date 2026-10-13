// frontend/src/lib/server/quiz-mock.js
// Test-Ersatz für Gridis Quiz-API, solange die echten Endpunkte noch fehlen.
// Gleiche Pfade, gleiche JSON-Formate, gleiche Statuscodes wie backend/docs/QUIZ_API.md.
// Daten liegen nur im Speicher des Dev-Servers (Neustart = alles weg).
// Vereinfachung: prüft NICHT, ob die Lehrkraft das Fach besitzt / der Schüler eingetragen ist.

let nextId = 1000;
const newId = () => nextId++;

const quizzes = []; // { id, class_subject_id, title, description, is_published, created_at, questions: [...] }
const results = []; // = quiz_results: { quiz_id, student_id, first_name, last_name, username, score, max_score, submitted_at, questions }
const seeded = new Set(); // Fächer, die schon ein Beispiel-Quiz bekommen haben

const now = () => new Date().toISOString().slice(0, 19);

function apiError(status, detail) {
	const e = new Error(detail);
	e.status = status;
	return e;
}

// ---------- Hilfsfunktionen ----------
const maxScore = (q) => q.questions.reduce((sum, x) => sum + x.points, 0);
const isLocked = (q) => results.some((r) => r.quiz_id === q.id);
const gapIndexes = (text) => [...new Set([...text.matchAll(/\{\{(\d+)\}\}/g)].map((m) => Number(m[1])))];
const norm = (s) => String(s ?? '').trim().toLowerCase();

function findQuiz(id) {
	const q = quizzes.find((x) => x.id === id);
	if (!q) throw apiError(404, 'Quiz nicht gefunden');
	return q;
}

// Format von Endpunkt 3 (mit Lösungen, nur Lehrkraft)
function teacherView(q) {
	return structuredClone({
		id: q.id,
		class_subject_id: q.class_subject_id,
		title: q.title,
		description: q.description,
		is_published: q.is_published,
		locked: isLocked(q),
		max_score: maxScore(q),
		questions: q.questions
	});
}

// Format von Endpunkt 8 (OHNE Lösungen, für Schüler)
function takeView(q) {
	return {
		id: q.id,
		title: q.title,
		description: q.description,
		max_score: maxScore(q),
		questions: q.questions.map((x) => {
			const base = { id: x.id, position: x.position, type: x.type, points: x.points, question_text: x.question_text };
			return x.type === 'gap'
				? { ...base, gap_count: gapIndexes(x.question_text).length }
				: { ...base, options: x.options.map((o) => ({ id: o.id, option_text: o.option_text })) };
		})
	};
}

// Body von Endpunkt 6/7 prüfen und in eine Frage (Format von 3.) umwandeln
function buildQuestion(body, position, id = newId()) {
	const { type, question_text, points } = body ?? {};
	if (!['mc', 'tf', 'gap'].includes(type)) throw apiError(400, 'Ungültiger Fragetyp');
	if (typeof question_text !== 'string' || !question_text.trim()) throw apiError(400, 'Fragetext fehlt');
	if (!Number.isInteger(points) || points < 1 || points > 100) throw apiError(400, 'points muss 1–100 sein');

	let options;
	if (type === 'mc') {
		const opts = body.options;
		if (!Array.isArray(opts) || opts.length < 2) throw apiError(400, 'Mindestens 2 Optionen');
		if (opts.some((o) => typeof o.option_text !== 'string' || !o.option_text.trim()))
			throw apiError(400, 'Leere Option');
		if (!opts.some((o) => o.is_correct)) throw apiError(400, 'Mindestens 1 richtige Option');
		options = opts.map((o, i) => ({
			id: newId(), option_text: o.option_text.trim(), is_correct: !!o.is_correct, gap_index: null, position: i + 1
		}));
	} else if (type === 'tf') {
		if (typeof body.correct !== 'boolean') throw apiError(400, 'correct fehlt');
		options = [
			{ id: newId(), option_text: 'Wahr', is_correct: body.correct, gap_index: null, position: 1 },
			{ id: newId(), option_text: 'Falsch', is_correct: !body.correct, gap_index: null, position: 2 }
		];
	} else {
		const idx = gapIndexes(question_text).sort((a, b) => a - b);
		const gaps = body.gaps;
		if (idx.length === 0 || !idx.every((n, i) => n === i)) throw apiError(400, 'Lücken müssen {{0}}, {{1}}, … heißen');
		if (!Array.isArray(gaps) || gaps.length !== idx.length) throw apiError(400, 'Anzahl der Lücken passt nicht zum Text');
		if (gaps.some((g) => !Array.isArray(g) || g.length === 0 || g.some((a) => typeof a !== 'string' || !a.trim())))
			throw apiError(400, 'Jede Lücke braucht mindestens eine Antwort');
		let pos = 1;
		options = gaps.flatMap((answers, gi) =>
			answers.map((a) => ({ id: newId(), option_text: a.trim(), is_correct: true, gap_index: gi, position: pos++ }))
		);
	}
	return { id, position, type, points, question_text: question_text.trim(), options };
}

// Bewertung (Regeln aus QUIZ_API.md): ganz oder gar nicht
function grade(quiz, answers) {
	if (!Array.isArray(answers)) throw apiError(422, 'answers fehlt');
	const byQuestion = new Map();
	for (const a of answers) {
		const q = quiz.questions.find((x) => x.id === a.question_id);
		if (!q) throw apiError(400, 'Frage gehört nicht zum Quiz');
		if (q.type !== 'gap')
			for (const oid of a.option_ids ?? [])
				if (!q.options.some((o) => o.id === oid)) throw apiError(400, 'Option gehört nicht zur Frage');
		byQuestion.set(q.id, a);
	}

	const questions = quiz.questions.map((q) => {
		const a = byQuestion.get(q.id);
		let correct = false;
		if (a && q.type === 'gap') {
			correct = gapIndexes(q.question_text).every((gi) =>
				q.options.some((o) => o.gap_index === gi && norm(o.option_text) === norm(a.gaps?.[gi]))
			);
		} else if (a) {
			const chosen = new Set(a.option_ids ?? []);
			const right = q.options.filter((o) => o.is_correct).map((o) => o.id);
			correct = chosen.size === right.length && right.every((oid) => chosen.has(oid));
		}
		return { question_id: q.id, correct, points_awarded: correct ? q.points : 0 };
	});
	return { score: questions.reduce((sum, x) => sum + x.points_awarded, 0), max_score: maxScore(quiz), questions };
}

// Beispiel-Quiz, damit man sofort etwas zum Testen hat (einmal pro Fach)
function seed(csId) {
	if (seeded.has(csId)) return;
	seeded.add(csId);
	const q = { id: newId(), class_subject_id: csId, title: 'Bruchrechnen (Beispiel)', description: 'Kapitel 4', is_published: true, created_at: now(), questions: [] };
	q.questions.push(
		buildQuestion({ type: 'mc', question_text: 'Welche Brüche sind gleich 1/2?', points: 2,
			options: [{ option_text: '2/4', is_correct: true }, { option_text: '3/4', is_correct: false }, { option_text: '4/8', is_correct: true }] }, 1),
		buildQuestion({ type: 'tf', question_text: '1/3 ist größer als 1/4.', points: 1, correct: true }, 2),
		buildQuestion({ type: 'gap', question_text: '3/4 als Dezimalzahl ist {{0}}.', points: 1, gaps: [['0,75', '0.75']] }, 3)
	);
	quizzes.push(q);
}

const isTeacher = (user) => user?.role === 'lehrkraft';
function requireTeacher(user) {
	if (!isTeacher(user)) throw apiError(403, 'Nur für Lehrkräfte');
}
function requireStudent(user) {
	if (user?.role !== 'schueler') throw apiError(403, 'Nur für Schüler');
}
function requireUnlocked(q) {
	if (isLocked(q)) throw apiError(409, 'Quiz ist gesperrt (Abgaben vorhanden)');
}

// ---------- Router: gleiche Pfade wie die echte API ----------
function route(method, path, body, user) {
	let m;

	// 1 + 2: /subjects/{cs_id}/quizzes
	if ((m = path.match(/^\/subjects\/(\d+)\/quizzes$/))) {
		const csId = Number(m[1]);
		seed(csId);
		if (method === 'GET') {
			const list = quizzes.filter((q) => q.class_subject_id === csId);
			if (user.role === 'schueler') {
				return [200, list.filter((q) => q.is_published).map((q) => {
					const r = results.find((x) => x.quiz_id === q.id && x.student_id === user.id);
					return {
						id: q.id, title: q.title, description: q.description,
						question_count: q.questions.length, max_score: maxScore(q),
						my_result: r ? { score: r.score, max_score: r.max_score, submitted_at: r.submitted_at } : null
					};
				})];
			}
			requireTeacher(user);
			return [200, list.map((q) => ({
				id: q.id, title: q.title, description: q.description, is_published: q.is_published,
				locked: isLocked(q), question_count: q.questions.length, max_score: maxScore(q),
				attempt_count: results.filter((r) => r.quiz_id === q.id).length, created_at: q.created_at
			}))];
		}
		if (method === 'POST') {
			requireTeacher(user);
			const title = typeof body?.title === 'string' ? body.title.trim() : '';
			if (!title || title.length > 150) throw apiError(400, 'Titel 1–150 Zeichen');
			const q = {
				id: newId(), class_subject_id: csId, title, description: body.description?.trim() || null,
				is_published: false, created_at: now(), questions: []
			};
			quizzes.push(q);
			return [201, teacherView(q)];
		}
	}

	// 3 + 4 + 5: /quizzes/{id}
	if ((m = path.match(/^\/quizzes\/(\d+)$/))) {
		requireTeacher(user);
		const q = findQuiz(Number(m[1]));
		if (method === 'GET') return [200, teacherView(q)];
		if (method === 'PUT') {
			body ??= {};
			if (('title' in body || 'description' in body) && isLocked(q)) throw apiError(409, 'Quiz ist gesperrt');
			if ('title' in body && (!body.title?.trim() || body.title.trim().length > 150)) throw apiError(400, 'Titel 1–150 Zeichen');
			if (body.is_published === true && q.questions.length === 0) throw apiError(400, 'Quiz hat keine Fragen');
			if ('title' in body) q.title = body.title.trim();
			if ('description' in body) q.description = body.description?.trim() || null;
			if ('is_published' in body) q.is_published = !!body.is_published;
			return [200, teacherView(q)];
		}
		if (method === 'DELETE') {
			requireUnlocked(q);
			quizzes.splice(quizzes.indexOf(q), 1);
			return [200, { status: 'geloescht', id: q.id }];
		}
	}

	// 6: POST /quizzes/{id}/questions
	if ((m = path.match(/^\/quizzes\/(\d+)\/questions$/)) && method === 'POST') {
		requireTeacher(user);
		const q = findQuiz(Number(m[1]));
		requireUnlocked(q);
		const question = buildQuestion(body, q.questions.length + 1);
		q.questions.push(question);
		return [201, structuredClone(question)];
	}

	// 7: PUT / DELETE /questions/{id}
	if ((m = path.match(/^\/questions\/(\d+)$/))) {
		requireTeacher(user);
		const qid = Number(m[1]);
		const q = quizzes.find((x) => x.questions.some((y) => y.id === qid));
		if (!q) throw apiError(404, 'Frage nicht gefunden');
		requireUnlocked(q);
		const i = q.questions.findIndex((y) => y.id === qid);
		if (method === 'PUT') {
			q.questions[i] = buildQuestion(body, q.questions[i].position, qid);
			return [200, structuredClone(q.questions[i])];
		}
		if (method === 'DELETE') {
			q.questions.splice(i, 1);
			q.questions.forEach((y, n) => (y.position = n + 1));
			return [200, { status: 'geloescht', id: qid }];
		}
	}

	// 8–11: /quizzes/{id}/take | submit | my-result | attempts
	if ((m = path.match(/^\/quizzes\/(\d+)\/(take|submit|my-result|attempts)$/))) {
		const q = findQuiz(Number(m[1]));
		const action = m[2];

		if (action === 'attempts' && method === 'GET') {
			requireTeacher(user);
			return [200, results
				.filter((r) => r.quiz_id === q.id)
				.map((r) => ({
					student_id: r.student_id, first_name: r.first_name, last_name: r.last_name, username: r.username,
					score: r.score, max_score: r.max_score, submitted_at: r.submitted_at
				}))];
		}

		requireStudent(user);
		const own = results.find((r) => r.quiz_id === q.id && r.student_id === user.id);
		const resultView = (r) => ({ score: r.score, max_score: r.max_score, submitted_at: r.submitted_at, questions: r.questions });

		if (action === 'my-result' && method === 'GET') {
			if (!own) throw apiError(404, 'Noch nicht abgegeben');
			return [200, resultView(own)];
		}
		if (!q.is_published) throw apiError(404, 'Quiz nicht gefunden');
		if (action === 'take' && method === 'GET') {
			if (own) throw apiError(409, 'Schon abgegeben');
			return [200, takeView(q)];
		}
		if (action === 'submit' && method === 'POST') {
			if (own) throw apiError(409, 'Schon abgegeben');
			const r = {
				quiz_id: q.id, student_id: user.id, first_name: user.first_name, last_name: user.last_name,
				username: user.username, submitted_at: now(), ...grade(q, body?.answers)
			};
			results.push(r);
			return [201, resultView(r)];
		}
	}

	throw apiError(404, `Mock: ${method} ${path} gibt es nicht`);
}

// Gibt eine echte Response zurück – genau wie fetch() bei der echten API
export async function mockApi(path, { method = 'GET', json, user }) {
	let status, data;
	try {
		[status, data] = route(method, path, json, user);
	} catch (e) {
		status = e.status ?? 500;
		data = { detail: e.message };
	}
	return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
}