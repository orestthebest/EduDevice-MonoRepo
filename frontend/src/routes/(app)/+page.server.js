import { apiJson } from '$lib/server/api.js';

// Dashboard: neueste Materialien aus den eigenen Fächern (die API filtert nach Rolle)
// (Login-Check passiert schon in (app)/+layout.server.js)
export async function load({ locals }) {
	return {
		recentMaterials: await apiJson('/materials/recent?limit=6', { token: locals.token })
	};
}