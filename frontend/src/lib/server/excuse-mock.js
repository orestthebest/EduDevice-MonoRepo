// frontend/src/lib/server/excuse-mock.js
// Test-Ersatz für Gridis Entschuldigungs-API, solange die echten Endpunkte fehlen.
// Gleiche Pfade und JSON-Formate wie mit Gridi abgesprochen.
// Daten liegen nur im Speicher des Dev-Servers (Neustart = alles weg).
// Vereinfachung: jede Lehrkraft gilt als Klassenvorstand aller Klassen.

let nextId = 1000;
const newId = () => nextId++;
const now = () => new Date().toISOString().slice(0, 19);

const absences = []; // = attendance: { id, student_id, date, start_time, subject, status, excuse_id }
const excuses = []; // { id, student_id, first_name, last_name, class_name, reason, status, teacher_comment, date_from, date_to, submitted_at, reviewed_at }
const seeded = new Set(); // Schüler, die schon Beispiel-Fehlstunden bekommen haben

function apiError(status, detail) {
	const e = new Error(detail);
	e.status = status;
	return e;
}

// Ein paar Fehlstunden in den letzten Tagen anlegen
function seedStudent(user) {
	if (seeded.has(user.id)) return;
	seeded.add(user.id);
	const day = (n) => new Date(Date.now() - n * 86400000).toISOString().slice(0, 10);
	const rows = [
		[day(1), '08:00:00', 'Mathematics', 'abwesend'],
		[day(1), '08:50:00', 'German', 'abwesend'],
		[day(1), '10:15:00', 'SEW', 'abwesend'],
		[day(4), '11:05:00', 'INSY', 'verspaetet'],
		[day(8), '13:00:00', 'ITP', 'abwesend']
	];
	for (const [date, start_time, subject, status] of rows) {
		absences.push({ id: newId(), student_id: user.id, date, start_time, subject, status, excuse_id: null });
	}
}

const excuseOf = (a) => excuses.find((e) => e.id === a.excuse_id);
const isUnexcused = (a) => !a.excuse_id || excuseOf(a)?.status === 'rejected';
const absenceView = ({ id, date, start_time, subject, status }) => ({ id, date, start_time, subject, status });

// Entschuldigung + ihre Fehlstunden (nach Datum sortiert)
function excuseView(e) {
	const list = absences
		.filter((a) => a.excuse_id === e.id)
		.sort((x, y) => (x.date + x.start_time).localeCompare(y.date + y.start_time))
		.map(absenceView);
	return { ...e, absences: list };
}

function route(method, path, body, user) {
	const url = new URL(path, 'http://mock');
	const p = url.pathname;
	const isStudent = user.role === 'schueler';
	const isTeacher = user.role === 'lehrkraft' || user.role === 'admin';

	// Schüler: eigene unentschuldigte Fehlstunden
	if (p === '/attendance/me' && method === 'GET') {
		if (!isStudent) throw apiError(403, 'Nur für Schüler');
		seedStudent(user);
		let list = absences.filter((a) => a.student_id === user.id);
		if (url.searchParams.get('unexcused') === 'true') list = list.filter(isUnexcused);
		return [200, list.map(absenceView)];
	}

	// Schüler: Entschuldigung einreichen
	if (p === '/excuses' && method === 'POST') {
		if (!isStudent) throw apiError(403, 'Nur für Schüler');
		const reason = String(body?.reason ?? '').trim();
		const ids = body?.attendance_ids ?? [];
		if (!reason) throw apiError(422, 'Begründung fehlt');
		if (!ids.length) throw apiError(422, 'Keine Fehlstunden ausgewählt');

		const picked = ids.map((id) => absences.find((a) => a.id === id && a.student_id === user.id));
		if (picked.some((a) => !a)) throw apiError(404, 'Fehlstunde nicht gefunden');
		if (picked.some((a) => !isUnexcused(a))) throw apiError(409, 'Fehlstunde ist schon entschuldigt');

		const dates = picked.map((a) => a.date).sort();
		const e = {
			id: newId(), student_id: user.id, first_name: user.first_name, last_name: user.last_name,
			class_name: '5B', reason, status: 'pending', teacher_comment: null,
			date_from: dates[0], date_to: dates.at(-1), submitted_at: now(), reviewed_at: null
		};
		excuses.push(e);
		for (const a of picked) a.excuse_id = e.id;
		return [201, excuseView(e)];
	}

	// Schüler: eigene Entschuldigungen
	if (p === '/excuses/me' && method === 'GET') {
		if (!isStudent) throw apiError(403, 'Nur für Schüler');
		const list = excuses.filter((e) => e.student_id === user.id).reverse();
		return [200, list.map(excuseView)];
	}

	// Klassenvorstand: Entschuldigungen der eigenen Klassen
	if (p === '/excuses/class-teacher' && method === 'GET') {
		if (!isTeacher) throw apiError(403, 'Nur für Lehrkräfte');
		const status = url.searchParams.get('status');
		let list = [...excuses].reverse();
		if (status) list = list.filter((e) => e.status === status);
		return [200, list.map(excuseView)];
	}

	// Klassenvorstand: annehmen / ablehnen
	const m = p.match(/^\/excuses\/(\d+)$/);
	if (m && method === 'PATCH') {
		if (!isTeacher) throw apiError(403, 'Nur für Lehrkräfte');
		const e = excuses.find((x) => x.id === Number(m[1]));
		if (!e) throw apiError(404, 'Entschuldigung nicht gefunden');
		if (!['accepted', 'rejected'].includes(body?.status)) throw apiError(422, 'Ungültiger Status');
		e.status = body.status;
		e.teacher_comment = body.teacher_comment?.trim() || null;
		e.reviewed_at = now();
		return [200, excuseView(e)];
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