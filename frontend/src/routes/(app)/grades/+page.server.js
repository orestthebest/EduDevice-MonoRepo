import { error } from '@sveltejs/kit';
import { apiJson } from '$lib/server/api.js';

// Notenstatistiken der Schülersicht (Ziel-M-3).
//
// Gerechnet wird in der API (/statistics/student/{id}), nicht hier. Die
// Notenordnung steht damit an genau einer Stelle; eine zweite Rechnung im
// Frontend würde früher oder später andere Noten anzeigen als die API.
//
// Die Rechteprüfung liegt ebenfalls in der API: Ein Schüler bekommt dort nur
// die eigenen Daten, eine Lehrkraft nur ihre eigenen Fächer. Würde erst die
// Oberfläche filtern, lieferte die Schnittstelle die Daten weiterhin an jeden
// aus, der sie direkt abfragt.
export async function load({ locals, url }) {
	const { user, token } = locals;

	// Lehrkraft und Administration dürfen eine Schülerin oder einen Schüler
	// auswählen; für Schüler ist der Parameter wirkungslos, weil die API ihn
	// ohnehin ablehnt.
	const requested = Number(url.searchParams.get('student'));
	const studentId = user.role === 'schueler' ? user.id : requested || user.id;

	if (user.role !== 'schueler' && !requested) {
		error(400, 'Please choose a student to show');
	}

	const stats = await apiJson(`/statistics/student/${studentId}`, { token });
	return { stats, isOwnView: studentId === user.id };
}
