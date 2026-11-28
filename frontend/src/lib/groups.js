// frontend/src/lib/groups.js
// Gruppen: jede Klasse hat fix die Gruppen X und Y.
// Wahlfächer (MED/NWTK/SYT) gehen über mehrere Klassen, z. B. sitzen 5A und 5B zusammen in MED.
export const SPLIT_GROUPS = ['X', 'Y'];

export const ELECTIVES = [
	{ key: 'MED', label: 'Medientechnik' },
	{ key: 'NWTK', label: 'Netzwerktechnik' },
	{ key: 'SYT', label: 'Systemtechnik' }
];

export const isElective = (group) => ELECTIVES.some((e) => e.key === group);
// "5B", "5B · X" oder "5A + 5B · MED" – für Karten, Listen und Auswahlfelder
// class_names gibt es nur bei Wahlfächern über mehrere Klassen
export function subjectTarget(s) {
	const classes = s.class_names?.length ? s.class_names.join(' + ') : s.class_name;
	return s.group ? `${classes} · ${s.group}` : classes;
}
