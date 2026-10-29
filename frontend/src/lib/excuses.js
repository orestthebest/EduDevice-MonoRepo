// frontend/src/lib/excuses.js
// Anzeige-Hilfen für das Entschuldigungssystem (Schüler- und Lehrerseite)

// Status-Badge: Funktionsfarben aus dem Corporate Design (Warning / Success / Error)
export const EXCUSE_STATUS = {
	pending: { label: 'Pending', class: 'bg-warning/15 text-[#b4730f]' },
	accepted: { label: 'Accepted', class: 'bg-success/12 text-success-dark' },
	rejected: { label: 'Rejected', class: 'bg-error/12 text-error' }
};

// attendance.status aus der DB -> Anzeigename
export const ABSENCE_LABEL = {
	abwesend: 'Absent',
	verspaetet: 'Late'
};

// "2026-10-28" -> "Wed, 28 Oct"
export function formatDay(value) {
	return new Date(value + 'T00:00:00').toLocaleDateString('en-GB', {
		weekday: 'short',
		day: 'numeric',
		month: 'short'
	});
}

// "08:00:00" -> "08:00"
export const formatTime = (value) => value.slice(0, 5);

// Ein Tag oder Zeitraum: "Wed, 28 Oct" bzw. "Mon, 26 Oct – Wed, 28 Oct"
export function formatRange(from, to) {
	return from === to ? formatDay(from) : `${formatDay(from)} – ${formatDay(to)}`;
}

// Fehlstunden nach Datum gruppieren: [{ date, items: [...] }], neuester Tag zuerst
export function groupByDate(absences) {
	const days = new Map();
	for (const a of absences) {
		if (!days.has(a.date)) days.set(a.date, []);
		days.get(a.date).push(a);
	}
	return [...days]
		.sort(([x], [y]) => y.localeCompare(x))
		.map(([date, items]) => ({ date, items: items.sort((a, b) => a.start_time.localeCompare(b.start_time)) }));
}