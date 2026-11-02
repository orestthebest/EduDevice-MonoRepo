// Hilfsfunktionen für die Notenanzeige (Schülersicht, Ziel-M-3).
//
// Die Notenskala der Schule läuft von 4 bis 10, wobei 10 die beste Note ist.
// Gerechnet wird ausschließlich in der API (services/grade_stats.py) — hier
// wird nur dargestellt. Wenn eine Zahl in dieser Datei berechnet würde, gäbe
// es zwei Stellen mit Notenlogik, und die beiden würden irgendwann
// auseinanderlaufen.

export const SCALE_MIN = 4;
export const SCALE_MAX = 10;

/** Note 4..10 auf 0..1 abbilden (für Balkenlängen und y-Positionen). */
export function scalePos(grade) {
	if (grade == null) return 0;
	const clamped = Math.min(SCALE_MAX, Math.max(SCALE_MIN, grade));
	return (clamped - SCALE_MIN) / (SCALE_MAX - SCALE_MIN);
}

/** Beschriftung und Farbe für den Status eines Fachs.
 *  Die Farbe steht nie allein — jedes Badge trägt zusätzlich diesen Text. */
export const STANDING = {
	failing: {
		label: 'At risk',
		hint: 'Below the pass mark',
		chip: 'bg-error/12 text-error',
		dot: 'bg-error'
	},
	fragile: {
		label: 'Close to the line',
		hint: 'Passing, but only just',
		chip: 'bg-warning/15 text-[#b4730f]',
		dot: 'bg-warning'
	},
	ok: {
		label: 'On track',
		hint: 'Comfortably passing',
		chip: 'bg-success/12 text-success-dark',
		dot: 'bg-success'
	},
	unknown: {
		label: 'Not graded yet',
		hint: 'No marks so far',
		chip: 'bg-surface text-subtle',
		dot: 'bg-muted'
	}
};

export function standingOf(key) {
	return STANDING[key] ?? STANDING.unknown;
}

/** Note für die Anzeige: 7.224 -> "7.22", null -> "–" */
export function fmtGrade(value, digits = 2) {
	if (value == null) return '–';
	return value.toFixed(digits).replace(/\.?0+$/, (m) => (m.includes('.') ? '' : m));
}

/** Kategorie aus der Datenbank -> lesbarer Name */
export const CATEGORY_LABEL = {
	homework: 'Homework',
	mini_test: 'Mini test',
	oral: 'Oral',
	presentation: 'Presentation',
	classwork: 'Classwork',
	participation: 'Participation',
	behaviour: 'Behaviour',
	schularbeit: 'Written exam',
	project: 'Project'
};

export function categoryLabel(key) {
	return CATEGORY_LABEL[key] ?? key;
}

/** Datum kurz: "2027-01-20" -> "20 Jan" */
export function shortDate(iso) {
	return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}
