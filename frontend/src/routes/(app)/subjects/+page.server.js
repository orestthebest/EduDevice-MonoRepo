import { getSubjectsForUser } from '$lib/server/subjects.js';

// Alle Fächer laden, die der eingeloggte User sehen darf
export async function load({ locals }) {
	return {
		subjects: await getSubjectsForUser(locals.user)
	};
}