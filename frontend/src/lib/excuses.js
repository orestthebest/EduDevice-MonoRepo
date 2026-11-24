// frontend/src/lib/excuses.js
// Anzeige-Hilfen für das Entschuldigungssystem (Schüler- und Lehrerseite)
import { m } from '$lib/paraglide/messages.js';
import { getLocale } from '$lib/paraglide/runtime.js';


// Status-Badge: Funktionsfarben aus dem Corporate Design (Warning / Success / Error)
// label ist ein Getter: der Text kommt erst beim Zugriff in der aktuellen Sprache
export const EXCUSE_STATUS = {
	pending: { get label() { return m.excuse_pending(); }, class: 'bg-warning/15 text-[#b4730f]' },
	accepted: { get label() { return m.excuse_accepted(); }, class: 'bg-success/12 text-success-dark' },
	rejected: { get label() { return m.excuse_rejected(); }, class: 'bg-error/12 text-error' }
};

// attendance.status aus der DB -> Anzeigename
export const ABSENCE_LABEL = {
	get abwesend() { return m.absence_absent(); },
	get verspaetet() { return m.absence_late(); }
};

// "2026-10-28" -> "Wed, 28 Oct"
export function formatDay(value) {
	return new Date(value + 'T00:00:00').toLocaleDateString(getLocale(), {
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