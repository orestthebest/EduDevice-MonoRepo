import { fail, redirect } from '@sveltejs/kit';
import { login } from '$lib/server/api.js';

// Wer schon eingeloggt ist, braucht die Login-Seite nicht
export function load({ locals }) {
	if (locals.user) redirect(303, '/');
}

// Formular-Wert -> Rolle in der DB
const ROLES = { student: 'schueler', teacher: 'lehrkraft', admin: 'admin' };

export const actions = {
	// Login über die REST-API (POST /auth/login). Die API prüft das Passwort
	// und gibt ein Token (JWT) zurück, das wir im Cookie speichern.
	login: async ({ request, cookies, url, getClientAddress }) => {
		const form = await request.formData();
		const username = form.get('username')?.toString().trim();
		const password = form.get('password')?.toString();
		const role = ROLES[form.get('role')?.toString()];

		if (!username || !password || !role) {
			return fail(400, { username, error: 'Please fill in all fields' });
		}

		// getClientAddress(): echte IP mitschicken, damit das Login-Limit pro Benutzer gilt
		const result = await login(username, password, getClientAddress());

		// Gleiche Meldung für "User existiert nicht" und "falsches Passwort"
		if (!result) {
			return fail(400, { username, error: 'Wrong username or password' });
		}

		// Gewählte Rolle muss zur Rolle des Accounts passen
		if (result.role !== role) {
			return fail(400, { username, error: 'This account does not have the selected role' });
		}

		// Token im Cookie speichern (so lange gültig wie das Token: 60 Minuten)
		cookies.set('token', result.access_token, {
			path: '/',
			httpOnly: true,
			sameSite: 'lax',
			secure: url.protocol === 'https:',
			maxAge: 60 * 60 * 8 // 8 Stunden, so lange wie das Token
		});

		redirect(303, '/');
	}
};