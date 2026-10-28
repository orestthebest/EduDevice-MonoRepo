import { fail } from '@sveltejs/kit';
import { api } from '$lib/server/api.js';



// Profilseite: die Daten kommen schon von /auth/me (hooks.server.js -> locals.user),
// deshalb ist hier kein extra API-Aufruf nötig.
export function load({ locals }) {
	const { id, first_name, last_name, username, email, role } = locals.user;
	return { profile: { id, first_name, last_name, username, email, role } };
}

export const actions = {
	// Eigene E-Mail ändern – die User-ID nimmt die API aus dem JWT
	updateEmail: async ({ request, locals }) => {
		const form = await request.formData();
		const email = form.get('email')?.toString().trim().toLowerCase() ?? '';

		// Gleiche Regel wie in der API (schemas.py)
		if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || email.length > 255) {
			return fail(400, { email, error: 'Please enter a valid email address' });
		}
		if (email === locals.user.email) {
			return fail(400, { email, error: 'This is already your email address' });
		}

		const res = await api('/users/me', { method: 'PATCH', token: locals.token, json: { email } });

		if (res.status === 409) return fail(409, { email, error: 'This email is already in use' });
		if (res.status === 400 || res.status === 422) return fail(400, { email, error: 'Please enter a valid email address' });
		if (res.status === 404 || res.status === 405) return fail(501, { email, error: 'Saving is not available yet' });
		if (!res.ok) return fail(res.status, { email, error: 'Could not save your email' });

		// Danach lädt SvelteKit die Seite neu -> hooks.server.js holt die neue E-Mail von /auth/me
		return { success: true };
	}
};