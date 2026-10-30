import { apiJson } from '$lib/server/api.js';
import { excuseApi } from '$lib/server/excuses.js';

// Dashboard: neueste Materialien aus den eigenen Fächern (die API filtert nach Rolle)
// (Login-Check passiert schon in (app)/+layout.server.js)
export async function load({ locals }) {
	const [recentMaterials, excuses] = await Promise.all([
		apiJson('/materials/recent?limit=6', { token: locals.token }),
		excuseSummary(locals)
	]);
	return { recentMaterials, excuses };
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