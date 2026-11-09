import { api, apiJson } from '$lib/server/api.js';
import { excuseApi } from '$lib/server/excuses.js';
import { todayISO } from '$lib/format.js';

// Dashboard: neueste Materialien aus den eigenen Fächern (die API filtert nach Rolle)
// (Login-Check passiert schon in (app)/+layout.server.js)
export async function load({ locals }) {
	const [recentMaterials, excuses, attendance] = await Promise.all([
		apiJson('/materials/recent?limit=6', { token: locals.token }),
		excuseSummary(locals),
		attendanceToday(locals)
	]);
	return { recentMaterials, excuses, attendance };
}

// Entschuldigungs-Karte am Dashboard.
// Fehler dürfen das Dashboard nicht blockieren -> dann null (Karte wird ausgeblendet)
async function excuseSummary(locals) {
	try {
		if (locals.user.role === 'schueler') {
			const [absRes, excRes] = await Promise.all([
				excuseApi('/attendance/me?unexcused=true', locals),
				excuseApi('/excuses/me', locals)
			]);
			if (!absRes.ok || !excRes.ok) return null;
			const [absences, excuses] = await Promise.all([absRes.json(), excRes.json()]);
			return {
				unexcused: absences.length,
				pending: excuses.filter((e) => e.status === 'pending').length,
				latest: excuses[0] ?? null // neueste zuerst
			};
		}
		if (locals.user.role !== 'schueler') {
			const res = await excuseApi('/excuses/class-teacher?status=pending', locals);
			if (!res.ok) return null;
			const pending = await res.json();
			return { pending: pending.length, latest: pending.slice(0, 3) };
		}

	} catch {
		/* API nicht erreichbar */
	}
	return null;
}


// Anwesenheits-Karte am Lehrer-Dashboard: heutige Stunden laut Stundenplan + ob schon erfasst.
// Fehler oder Wochenende dürfen das Dashboard nicht blockieren -> null bzw. leere Liste
async function attendanceToday(locals) {
	if (locals.user.role !== 'lehrkraft') return null;
	try {
		const token = locals.token;
		const date = todayISO();
		const subjects = (await apiJson('/subjects', { token })).filter((s) => s.teacher_id === locals.user.id);

		const perSubject = await Promise.all(
			subjects.map(async (s) => {
				const q = `class_subject_id=${s.id}`;
				const [slotsRes, histRes] = await Promise.all([
					api(`/attendance/slots?${q}&date=${date}`, { token }),
					api(`/attendance/history?${q}`, { token })
				]);
				if (!slotsRes.ok || !histRes.ok) return []; // 400 = Wochenende
				const [slots, history] = await Promise.all([slotsRes.json(), histRes.json()]);

				const done = new Set(history.filter((h) => h.date === date).map((h) => h.start_time));
				return slots.map((slot) => ({
					subjectId: s.id,
					subject: s.subject_name,
					className: s.class_name,
					start: slot.start_time.slice(0, 5),
					room: slot.room,
					recorded: done.has(slot.start_time)
				}));
			})
		);

		return { date, lessons: perSubject.flat().sort((a, b) => a.start.localeCompare(b.start)) };
	} catch {
		return null; // API nicht erreichbar
	}
}