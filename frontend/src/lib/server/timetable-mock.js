// frontend/src/lib/server/timetable-mock.js
// Test-Ersatz für Gridis Stundenplan-API (Teil 3), solange GET /timetable/week noch fehlt.
// Gleiches Format wie vereinbart: eine Zeile pro Stunde + Tage ohne Unterricht.
// Liefert für jede Woche denselben Beispiel-Stundenplan (angelehnt an die 5B).
import { PERIODS, WEEKDAYS, weekStart, addDays } from '$lib/timetable.js';
import { SPLIT_GROUPS, isElective } from '$lib/groups.js';

// [Wochentag, von, bis, Fach, Raum, Lehrer, class_subject_id, entfällt?]
const PLAN = [
	['Mo', 1, 2, 'SEW', 'PR3', 'CER', 1],
	['Mo', 1, 2, 'NWTK', 'S-LAB', 'ROA', 2], // Gruppenteilung: parallel zu SEW
	['Mo', 3, 4, 'D', 'K23', 'PAE', 3],
	['Mo', 5, 6, 'AM', 'K22', 'MOM', 4],
	['Mo', 8, 9, 'ITP', 'SYTLAB', 'BRR', 5],
	['Di', 1, 1, 'E', 'K16', 'EGA', 6],
	['Di', 2, 3, 'INSY', 'PR1', 'OPP', 7],
	['Di', 4, 5, 'MEDT', 'MLAB', 'PFM', 8],
	['Di', 6, 6, 'D', 'K23', 'PAE', 3],
	['Mi', 1, 2, 'SYT', 'SYTLAB', 'UNH', 9],
	['Mi', 3, 4, 'WIR', 'K25', 'SCG', 10, true], // Beispiel: entfällt
	['Mi', 5, 6, 'INSY', 'SW2', 'CER', 7],
	['Do', 1, 2, 'WAE', 'PR1', 'OPP', 11],
	['Do', 3, 3, 'AM', 'K22', 'MOM', 4],
	['Do', 4, 4, 'E', 'K22', 'EGA', 6],
	['Do', 5, 6, 'SEW', 'SW2', 'CER', 1],
	['Do', 8, 9, 'ITP', 'K21', 'PFM', 5],
	['Fr', 1, 2, 'MEDT', 'MLAB', 'PFM', 8],
	['Fr', 3, 4, 'NWTK', 'S-LAB', 'ROA', 2],
	['Fr', 5, 5, 'D', 'K22', 'PAE', 3],
	['Fr', 6, 6, 'AM', 'K22', 'MOM', 4]
];

// Gruppe pro Fach im Beispielplan (fehlt = ganze Klasse): SEW und NWTK am Montag laufen parallel
const GROUP_OF = { 1: 'X', 2: 'Y', 8: 'MED' };

// Lehrkraft: nur die eigenen Stunden, in verschiedenen Klassen
// [Wochentag, von, bis, Fach, Raum, Klasse, class_subject_id, entfällt?]
const TEACHER_PLAN = [
	['Mo', 1, 2, 'SEW', 'PR3', '5B', 1],
	['Mo', 5, 6, 'SEW', 'PR3', '4A', 21],
	['Di', 2, 3, 'INSY', 'PR1', '5B', 7],
	['Di', 8, 9, 'SEW', 'SW2', '3B', 22],
	['Mi', 5, 6, 'INSY', 'SW2', '5B', 7],
	['Do', 1, 2, 'SEW', 'PR3', '4A', 21, true], // Beispiel: entfällt
	['Do', 5, 6, 'SEW', 'SW2', '5B', 1],
	['Fr', 3, 4, 'INSY', 'PR1', '3B', 23]
];

// Tage ohne Unterricht (wie school_calendar)
const DAYS_OFF = [
	{ date: '2026-11-27', day_type: 'autonomous_day', note: 'Bridge day before Independence Day' },
	{ date: '2026-12-24', day_type: 'break', note: 'Christmas break' },
	{ date: '2026-12-25', day_type: 'holiday', note: 'Christmas' }
];

function week(date, isTeacher) {
	const monday = weekStart(date);
	const dates = Object.fromEntries(WEEKDAYS.map((w, i) => [w.key, addDays(monday, i)]));
	const daysOff = DAYS_OFF.filter((d) => Object.values(dates).includes(d.date));

	const lessons = [];
	const plan = isTeacher ? TEACHER_PLAN : PLAN;
	for (const [weekday, from, to, subject, room, who, csId, cancelled = false] of plan) {
		const day = dates[weekday];
		if (daysOff.some((d) => d.date === day)) continue;
		for (let p = from; p <= to; p++) {
			lessons.push({
				lesson_id: Number(day.replaceAll('-', '')) * 100 + p * 10 + (csId % 10),
				date: day,
				period: p,
				start_time: PERIODS[p - 1].start,
				end_time: PERIODS[p - 1].end,
				class_subject_id: csId,
				subject,
				class_name: isTeacher ? who : '5B',
				teacher: isTeacher ? null : who,
				group: GROUP_OF[csId] ?? null,
				room,
				cancelled
			});
		}
	}
	return {
		week_start: monday,
		lessons,
		calendar: daysOff.map((d) => ({ ...d, has_lessons: false, timetable_weekday: null }))
	};
}

// ---------- Verwaltung (M-4): Stundenplan einer Klasse ----------
// Nur im Speicher des Dev-Servers (Neustart = leer). Eine Zeile pro Stunde wie in der DB.
const classSlots = new Map(); // class_id -> [{ id, class_subject_id, weekday, period, start_time, end_time, room }]

let nextSlotId = 1;

const mockError = (status, detail) => [status, { detail }];
const allSlots = () => [...classSlots.values()].flat();

// ---------- Räume (Stammdaten) ----------
// Startwerte = die Räume aus dem Beispielplan
const rooms = ['K16', 'K21', 'K22', 'K23', 'K25', 'K26', 'MLAB', 'PR1', 'PR3', 'S-LAB', 'SW2', 'SYTLAB']
	.map((name, i) => ({ id: i + 1, name, capacity: null }));
let nextRoomId = rooms.length + 1;

const roomById = (id) => rooms.find((r) => r.id === Number(id)) ?? null;
const sortedRooms = () => [...rooms].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));

// POST /rooms (id = null) und PUT /rooms/{id}: Name prüfen, Kapazität ist optional
function saveRoom(json, id = null) {
	const name = (json?.name ?? '').trim();
	const capacity = json?.capacity ? Number(json.capacity) : null;
	if (!name || name.length > 50) return mockError(422, 'Ungültiger Raumname');
	if (capacity !== null && !(capacity > 0)) return mockError(422, 'Ungültige Kapazität');
	if (rooms.some((r) => r.id !== id && r.name.toLowerCase() === name.toLowerCase())) {
		return mockError(409, `Room ${name} already exists`);
	}

	if (id === null) {
		const room = { id: nextRoomId++, name, capacity };
		rooms.push(room);
		return [201, room];
	}
	const room = roomById(id);
	if (!room) return mockError(404, 'Raum nicht gefunden');
	Object.assign(room, { name, capacity });
	// Neuen Namen im Stundenplan mitziehen (in der echten DB passiert das über room_id von selbst)
	for (const s of allSlots()) if (s.room_id === room.id) s.room = name;
	return [200, room];
}

// DELETE /rooms/{id}: nur wenn darin kein Unterricht mehr stattfindet
function deleteRoom(id) {
	const room = roomById(id);
	if (!room) return mockError(404, 'Raum nicht gefunden');
	if (allSlots().some((s) => s.room_id === room.id)) {
		return mockError(409, `Room ${room.name} is still used in the timetable`);
	}
	rooms.splice(rooms.indexOf(room), 1);
	return [204, null];
}

// GET /rooms/availability?weekday=Di&period_from=3&period_to=4&ignore=5,6
// -> alle Räume, belegte mit taken_by = Klasse. ignore = Stunden des Blocks, der gerade bearbeitet wird
function availability(params) {
	const weekday = params.get('weekday');
	const from = Number(params.get('period_from'));
	const to = Number(params.get('period_to'));
	const ignore = (params.get('ignore') ?? '').split(',').filter(Boolean).map(Number);
	const busy = allSlots().filter(
		(s) => s.weekday === weekday && s.period >= from && s.period <= to && !ignore.includes(s.id)
	);
	return [200, sortedRooms().map((r) => ({ ...r, taken_by: busy.find((s) => s.room_id === r.id)?.class_name ?? null }))];
}

// POST /timetable: eine Zeile pro Stunde anlegen, vorher Überschneidungen prüfen.
// extra = { class_id, class_name, teacher_id, teacher_name } kommt nur beim Mock mit (die echte API kennt das selbst).
// Vereinfachung: prüft Lehrkraft und Raum, aber NICHT die einzelnen Schüler.
function createSlots(json, extra = {}) {
	const { class_subject_id, weekday, period_from, period_to, room_id = null } = json ?? {};
	const room = room_id ? roomById(room_id) : null;
	if (room_id && !room) return mockError(422, 'Raum nicht gefunden');
	if (!class_subject_id || !extra.class_id) return mockError(422, 'class_subject_id fehlt');
	if (!WEEKDAYS.some((w) => w.key === weekday)) return mockError(422, 'Ungültiger Wochentag');
	if (!(period_from >= 1 && period_to <= PERIODS.length && period_from <= period_to)) {
		return mockError(422, 'Ungültige Stunden');
	}

	const all = allSlots();
	for (let p = period_from; p <= period_to; p++) {
		const busy = all.filter((s) => s.weekday === weekday && s.period === p);
		const teacher = busy.find((s) => s.teacher_id === extra.teacher_id);
		if (teacher) {
			return mockError(409, `${extra.teacher_name ?? 'The teacher'} already teaches class ${teacher.class_name} in period ${p}`);
		}
		const usedRoom = room && busy.find((s) => s.room_id === room.id);
		if (usedRoom) return mockError(409, `Room ${room.name} is already used by class ${usedRoom.class_name} in period ${p}`);
	}

	const created = [];
	for (let p = period_from; p <= period_to; p++) {
		created.push({
			id: nextSlotId++,
			class_subject_id,
			weekday,
			period: p,
			start_time: PERIODS[p - 1].start,
			end_time: PERIODS[p - 1].end,
			room_id: room?.id ?? null,
			room: room?.name ?? null,
			// nur für die Prüfungen im Mock
			class_name: extra.class_name,
			teacher_id: extra.teacher_id
		});
	}
	classSlots.set(extra.class_id, [...(classSlots.get(extra.class_id) ?? []), ...created]);
	return [201, created];
}

// DELETE /timetable/{id}: eine Stunde löschen (im Mock immer endgültig, ohne valid_to)
function deleteSlot(id) {
	for (const [classId, slots] of classSlots) {
		if (slots.some((s) => s.id === id)) {
			classSlots.set(classId, slots.filter((s) => s.id !== id));
			return [204, null];
		}
	}
	return mockError(404, 'Stundenplan-Eintrag nicht gefunden');
}

// ---------- Gruppe (X/Y) + Wahlfach pro SchülerIn ----------
// class_id -> Map(student_id -> { group, elective })
const studentGroups = new Map();

const groupList = (classId) =>
	[...(studentGroups.get(classId) ?? new Map())].map(([student_id, a]) => ({ student_id, ...a }));

// PUT /classes/{id}/groups { assignments: [{ student_id, group, elective }] } – speichert alle auf einmal
function setGroups(classId, json) {
	const list = json?.assignments;
	if (!Array.isArray(list)) return mockError(422, 'assignments fehlt');
	for (const a of list) {
		if (a.group && !SPLIT_GROUPS.includes(a.group)) return mockError(422, `Ungültige Gruppe ${a.group}`);
		if (a.elective && !isElective(a.elective)) return mockError(422, `Ungültiges Wahlfach ${a.elective}`);
	}

	const map = studentGroups.get(classId) ?? new Map();
	for (const a of list) map.set(Number(a.student_id), { group: a.group || null, elective: a.elective || null });
	studentGroups.set(classId, map);
	return [200, groupList(classId)];
}

function route(method, url, json, user, extra) {
	if (method === 'GET' && url.pathname === '/timetable/week') {
		const date = url.searchParams.get('date') ?? new Date().toISOString().slice(0, 10);
		return [200, week(date, user?.role === 'lehrkraft')]; // Lehrkraft: nur eigene Stunden
	}

	const cls = url.pathname.match(/^\/timetable\/class\/(\d+)$/);
	if (method === 'GET' && cls) return [200, classSlots.get(Number(cls[1])) ?? []];
    
	if (method === 'POST' && url.pathname === '/timetable') return createSlots(json, extra);

    
	const one = url.pathname.match(/^\/timetable\/(\d+)$/);
	if (method === 'DELETE' && one) return deleteSlot(Number(one[1]));

	// ---------- Gruppen ----------
	const grp = url.pathname.match(/^\/classes\/(\d+)\/groups$/);
	if (grp && method === 'GET') return [200, groupList(Number(grp[1]))];
	if (grp && method === 'PUT') return setGroups(Number(grp[1]), json);

	// ---------- Räume ----------
	if (url.pathname === '/rooms') {
		if (method === 'GET') return [200, sortedRooms()];
		if (method === 'POST') return saveRoom(json);
	}
	if (method === 'GET' && url.pathname === '/rooms/availability') return availability(url.searchParams);
	const room = url.pathname.match(/^\/rooms\/(\d+)$/);
	if (room && method === 'PUT') return saveRoom(json, Number(room[1]));
	if (room && method === 'DELETE') return deleteRoom(Number(room[1]));

	return [404, { detail: `Mock: ${method} ${url.pathname} gibt es noch nicht` }];
}

export async function mockApi(path, { method = 'GET', json, user, extra } = {}) {
	const [status, data] = route(method, new URL(path, 'http://mock'), json, user, extra);
    if (status === 204) return new Response(null, { status }); // 204 darf keinen Body haben
	return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
}