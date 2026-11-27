// Hilfsfunktionen für die Notenanzeige (Schülersicht, Ziel-M-3).
//
// Die Notenskala der Schule läuft von 4 bis 10, wobei 10 die beste Note ist.
// Gerechnet wird ausschließlich in der API (services/grade_stats.py) — hier
// wird nur dargestellt. Wenn eine Zahl in dieser Datei berechnet würde, gäbe
// es zwei Stellen mit Notenlogik, und die beiden würden irgendwann
// auseinanderlaufen.
import { m } from '$lib/paraglide/messages.js';
import { getLocale } from '$lib/paraglide/runtime.js';

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
		get label() { return m.grades_at_risk(); },
		get hint() { return m.grades_at_risk_hint(); },
		chip: 'bg-error/12 text-error',
		dot: 'bg-error'
	},
	fragile: {
		get label() { return m.grades_close(); },
		hint: 'Passing, but only just',
		chip: 'bg-warning/15 text-[#b4730f]',
		dot: 'bg-warning'
	},
	ok: {
		get label() { return m.grades_on_track(); },
		get hint() { return m.grades_on_track_hint(); },
		chip: 'bg-success/12 text-success-dark',
		dot: 'bg-success'
	},
	unknown: {
		get label() { return m.grades_not_graded(); },
		get hint() { return m.grades_not_graded_hint(); },
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
	return value.toFixed(digits).replace(/\.?0+$/, (match) => (match.includes('.') ? '' : match));
}

/** Veränderung mit Vorzeichen: 0.88 -> "+0.88", -0.21 -> "−0.21" (echtes Minuszeichen) */
export function fmtSigned(value, digits = 2) {
	if (value == null) return '–';
	const text = fmtGrade(Math.abs(value), digits);
	return value > 0 ? `+${text}` : value < 0 ? `−${text}` : '±0';
}

/** Kategorie aus der Datenbank -> lesbarer Name */
export const CATEGORY_LABEL = {
	get homework() { return m.cat_homework(); },
	get mini_test() { return m.cat_mini_test(); },
	get oral() { return m.cat_oral(); },
	get presentation() { return m.cat_presentation(); },
	get classwork() { return m.cat_classwork(); },
	get participation() { return m.cat_participation(); },
	get behaviour() { return m.cat_behaviour(); },
	get schularbeit() { return m.cat_schularbeit(); },
	get project() { return m.cat_project(); }
};

export function categoryLabel(key) {
	return CATEGORY_LABEL[key] ?? key;
}

/** Datum kurz: "2027-01-20" -> "20 Jan" */
export function shortDate(iso) {
	return new Date(iso).toLocaleDateString(getLocale(), { day: 'numeric', month: 'short' });
}
