// frontend/src/lib/timetable.js
// Stundenplan: Stundenraster der Schule + Hilfsfunktionen für Ansicht (M-3) und Verwaltung (M-4)

// Stundenraster (wie in WebUntis). Eine Unterrichtseinheit = eine Stunde aus dieser Liste.
export const PERIODS = [
	{ period: 1, start: '07:45', end: '08:30' },
	{ period: 2, start: '08:35', end: '09:20' },
	{ period: 3, start: '09:35', end: '10:20' },
	{ period: 4, start: '10:25', end: '11:10' },
	{ period: 5, start: '11:20', end: '12:05' },
	{ period: 6, start: '12:10', end: '12:55' },
	{ period: 7, start: '13:00', end: '13:45' },
	{ period: 8, start: '13:50', end: '14:35' },
	{ period: 9, start: '14:40', end: '15:25' },
	{ period: 10, start: '15:30', end: '16:15' },
	{ period: 11, start: '16:20', end: '17:05' }
];

// Wochentage wie in der DB ('Mo' ...) + Anzeigename
export const WEEKDAYS = [
	{ key: 'Mo', label: 'Mon' },
	{ key: 'Di', label: 'Tue' },
	{ key: 'Mi', label: 'Wed' },
	{ key: 'Do', label: 'Thu' },
	{ key: 'Fr', label: 'Fri' }
];

// "07:45:00" oder "07:45" -> Stunde 1 (null, wenn die Zeit nicht im Raster liegt)
export function periodOf(time) {
	return PERIODS.find((p) => p.start === String(time).slice(0, 5))?.period ?? null;
}

// ---------- Datum (immer "YYYY-MM-DD", lokale Zeit) ----------
const toISO = (d) =>
	`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const fromISO = (iso) => new Date(iso + 'T00:00:00');

export function addDays(iso, n) {
	const d = fromISO(iso);
	d.setDate(d.getDate() + n);
	return toISO(d);
}

// Montag der Woche, in der das Datum liegt (Sa/So -> Montag der nächsten Woche)
export function weekStart(iso) {
	const day = fromISO(iso).getDay(); // 0 = So, 6 = Sa
	if (day === 0) return addDays(iso, 1);
	if (day === 6) return addDays(iso, 2);
	return addDays(iso, 1 - day);
}

// Mo–Fr einer Woche: [{ key: 'Mo', label: 'Mon', date: '2026-11-09' }, ...]
export const weekDays = (monday) => WEEKDAYS.map((w, i) => ({ ...w, date: addDays(monday, i) }));

// "2026-11-09" -> "09.11."
export const shortDate = (iso) => `${iso.slice(8, 10)}.${iso.slice(5, 7)}.`;

// ---------- Blöcke ----------
// Die API liefert eine Zeile pro Stunde. Für die Ansicht werden aufeinanderfolgende Stunden
// desselben Fachs (gleicher Tag, gleicher Raum, gleicher Status) zu einem Block zusammengefasst:
// Doppelstunde 5+6 -> ein Block { from: 5, to: 6 }.
// key = Tag ('date' in der Wochenansicht, 'weekday' in der Verwaltung)
export function toBlocks(lessons, key = 'date') {
	const sorted = lessons
		.map((l) => ({ ...l, period: l.period ?? periodOf(l.start_time) }))
		.filter((l) => l.period)
		.sort((a, b) => String(a[key]).localeCompare(String(b[key])) || a.class_subject_id - b.class_subject_id || a.period - b.period);

	const blocks = [];
	for (const l of sorted) {
		const last = blocks.at(-1);
		const same = last && last.day === l[key] && last.class_subject_id === l.class_subject_id &&
			last.room === l.room && Boolean(last.cancelled) === Boolean(l.cancelled) && last.to === l.period - 1;
		if (same) {
			last.to = l.period;
			last.items.push(l);
		} else {
			blocks.push({ ...l, day: l[key], from: l.period, to: l.period, items: [l] });
		}
	}
	return layoutDays(blocks);
}

// Parallele Stunden (z. B. Gruppenteilung) nebeneinander statt übereinander:
// jeder Block bekommt col (Spalte) und cols (Anzahl Spalten in seiner Gruppe)
function layoutDays(blocks) {
	for (const dayBlocks of groupByDay(blocks).values()) {
		dayBlocks.sort((a, b) => a.from - b.from || b.to - a.to);
		let group = [];
		let groupEnd = 0;
		const close = () => {
			const cols = Math.max(1, ...group.map((b) => b.col + 1));
			group.forEach((b) => (b.cols = cols));
		};
		for (const b of dayBlocks) {
			if (group.length && b.from > groupEnd) {
				close();
				group = [];
			}
			// erste Spalte, in der der Block nicht mit einem anderen überlappt
			let col = 0;
			while (group.some((g) => g.col === col && g.to >= b.from)) col++;
			b.col = col;
			group.push(b);
			groupEnd = Math.max(groupEnd, b.to);
		}
		if (group.length) close();
	}
	return blocks;
}

function groupByDay(blocks) {
	const map = new Map();
	for (const b of blocks) {
		if (!map.has(b.day)) map.set(b.day, []);
		map.get(b.day).push(b);
	}
	return map;
}

// ---------- Farben ----------
// Jedes Fach bekommt immer dieselbe Markenfarbe (für den Balken links am Block).
// Nur die vier Farben des Brand-Verlaufs – Funktionsfarben (grün/gelb/rot) sind für Status reserviert.
const SUBJECT_COLORS = ['#8b2fe8', '#00a3ff', '#4a5ff7', '#433896'];

export function subjectColor(name = '') {
	let hash = 0;
	for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
	return SUBJECT_COLORS[hash % SUBJECT_COLORS.length];
}