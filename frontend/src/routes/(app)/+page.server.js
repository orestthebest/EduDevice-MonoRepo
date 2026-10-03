import { getRecentMaterials } from '$lib/server/subjects.js';

// Dashboard: neueste Materialien laden
// (Login-Check passiert schon in (app)/+layout.server.js)
export async function load({ locals }) {
	return {
		recentMaterials: await getRecentMaterials(locals.user)
	};
}