import { redirect } from '@sveltejs/kit';

// Schützt alle Seiten in (app): ohne Login -> /login
export function load({ locals }) {
	if (!locals.user) redirect(303, '/login');

	// Nur die Felder weitergeben, die das Frontend braucht (kein password_hash!)
	const { id, first_name, last_name, username, role } = locals.user;
	return { user: { id, first_name, last_name, username, role } };
}