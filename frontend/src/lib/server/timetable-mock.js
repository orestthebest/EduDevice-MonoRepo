// frontend/src/lib/server/timetable-mock.js
// Test-Ersatz für Gridis Stundenplan-API (Teil 3), solange GET /timetable/week noch fehlt.
// Gleiches Format wie vereinbart: eine Zeile pro Stunde + Tage ohne Unterricht.
// Liefert für jede Woche denselben Beispiel-Stundenplan (angelehnt an die 5B).
import { PERIODS, WEEKDAYS, weekStart, addDays } from '$lib/timetable.js';

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

// Tage ohne Unterricht (wie school_calendar)
const DAYS_OFF = [
	{ date: '2026-11-27', day_type: 'autonomous_day', note: 'Bridge day before Independence Day' },
	{ date: '2026-12-24', day_type: 'break', note: 'Christmas break' },
	{ date: '2026-12-25', day_type: 'holiday', note: 'Christmas' }
];

function week(date) {
	const monday = weekStart(date);
	const dates = Object.fromEntries(WEEKDAYS.map((w, i) => [w.key, addDays(monday, i)]));
	const daysOff = DAYS_OFF.filter((d) => Object.values(dates).includes(d.date));

	const lessons = [];
	for (const [weekday, from, to, subject, room, teacher, csId, cancelled = false] of PLAN) {
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
				class_name: '5B',
				teacher,
				room,
				cancelled
			});
		}
	}
	return { week_start: monday, lessons, days_off: daysOff };
}

export async function mockApi(path) {
	const url = new URL(path, 'http://mock');
	let status = 200;
	let data;
	if (url.pathname === '/timetable/week') {
		data = week(url.searchParams.get('date') ?? new Date().toISOString().slice(0, 10));
	} else {
		status = 404;
		data = { detail: `Mock: ${url.pathname} gibt es noch nicht` };
	}
	return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
}