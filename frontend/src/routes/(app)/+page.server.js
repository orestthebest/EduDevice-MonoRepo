import { redirect } from '@sveltejs/kit';

// Nicht eingeloggt -> zum Login.
export async function load({ locals }) {
	if (!locals.user) redirect(303, '/login');
	return { user: locals.user };
}