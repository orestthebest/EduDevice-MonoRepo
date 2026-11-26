import { fail } from '@sveltejs/kit';
import { api } from '$lib/server/api.js';
import { m } from '$lib/paraglide/messages.js';

// Profilseite: die Daten kommen schon von /auth/me (hooks.server.js -> locals.user),
// deshalb ist hier kein extra API-Aufruf nötig.
export function load({ locals }) {
	const { id, first_name, last_name, username, email, role, profile_image } = locals.user;
	return { profile: { id, first_name, last_name, username, email, role, profile_image } };
}

export const actions = {
	
	// Eigenes Passwort ändern – das aktuelle Passwort prüft die API
	updatePassword: async ({ request, locals }) => {
		const form = await request.formData();
		const current_password = form.get('current_password')?.toString() ?? '';
		const new_password = form.get('new_password')?.toString() ?? '';
		const confirm_password = form.get('confirm_password')?.toString() ?? '';

		// Passwörter nie zurück an die Seite schicken, nur die Fehlermeldung
		if (!current_password || !new_password) {
			return fail(400, { passwordError: m.error_fill_all() });
		}
		if (new_password.length < 8 || new_password.length > 72) {
			return fail(400, { passwordError: m.prof_err_password_length() });
		}
		if (new_password !== confirm_password) {
			return fail(400, { passwordError: m.prof_err_password_mismatch() });
		}
		if (new_password === current_password) {
			return fail(400, { passwordError: m.prof_err_password_same() });
		}

		const res = await api('/users/me/password', {
			method: 'POST',
			token: locals.token,
			json: { current_password, new_password }
		});

		if (res.status === 400) return fail(400, { passwordError: m.prof_err_password_wrong() });
		if (res.status === 422) return fail(400, { passwordError: m.prof_err_password_length() });
		if (res.status === 429) return fail(429, { passwordError: m.prof_err_too_many() });
		if (!res.ok) return fail(res.status, { passwordError: m.prof_err_password_save()});

		return { passwordSuccess: true };
	},

	// Eigenen Username ändern – gleiche Regeln wie bei Register (3–50 Zeichen)
	updateUsername: async ({ request, locals }) => {
		const form = await request.formData();
		const username = form.get('username')?.toString().trim() ?? '';

		if (username.length < 3 || username.length > 50) {
			return fail(400, { username, usernameError: m.prof_err_username_length() });
		}
		if (username === locals.user.username) {
			return fail(400, { username, usernameError: m.prof_err_username_same() });
		}

		const res = await api('/users/me', { method: 'PATCH', token: locals.token, json: { username } });

		if (res.status === 409) return fail(409, { username, usernameError: m.error_username_taken() });
		if (res.status === 422) return fail(400, { username, usernameError: m.prof_err_username_length() });
		if (!res.ok) return fail(res.status, { username, usernameError: m.prof_err_username_save() });

		// Token bleibt gültig (enthält die User-ID), /auth/me liefert danach den neuen Username
		return { usernameSuccess: true };
	},
	// Eigene E-Mail ändern – die User-ID nimmt die API aus dem JWT
	updateEmail: async ({ request, locals }) => {
		const form = await request.formData();
		// trim() ist Pflicht: Leerzeichen am Rand gibt bei der API 422
		const email = form.get('email')?.toString().trim().toLowerCase() ?? '';

		// Gleiche Regel wie in der API (schemas.py)
		if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || email.length > 255) {
			return fail(400, { email, error: m.prof_err_email_invalid() });
		}
		if (email === locals.user.email) {
			return fail(400, { email, error: m.prof_err_email_same() });
		}

		const res = await api('/users/me', { method: 'PATCH', token: locals.token, json: { email } });

		if (res.status === 409) return fail(409, { email, error: m.prof_err_email_taken() });
		if (res.status === 422) return fail(400, { email, error: m.prof_err_email_invalid() });
		if (!res.ok) return fail(res.status, { email, error: m.prof_err_email_save() });

		// Danach lädt SvelteKit die Seite neu -> hooks.server.js holt die neue E-Mail von /auth/me
		return { success: true };
	},

	// Profilbild hochladen – Prüfen, Zuschneiden auf 256x256 und WebP macht die API
	uploadAvatar: async ({ request, locals }) => {
		const form = await request.formData();
		const file = form.get('file');

		if (!(file instanceof File) || file.size === 0) {
			return fail(400, { avatarError: m.prof_err_choose_image() });
		}
		if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
			return fail(400, { avatarError: m.prof_err_image_type() });
		}
		if (file.size > 2 * 1024 * 1024) {
			return fail(400, { avatarError: m.prof_err_image_size() });
		}

		const body = new FormData();
		body.append('file', file);
		const res = await api('/users/me/avatar', { method: 'POST', token: locals.token, form: body });

		if (res.status === 413) return fail(400, { avatarError: m.prof_err_image_size() });
		if (res.status === 400) return fail(400, { avatarError: m.prof_err_image_invalid() });
		if (!res.ok) return fail(res.status, { avatarError: m.prof_err_upload() });

		return { avatarSuccess: m.prof_picture_updated() };
	},

	// Profilbild entfernen -> wieder Initialen
	removeAvatar: async ({ locals }) => {
		const res = await api('/users/me/avatar', { method: 'DELETE', token: locals.token });
		if (!res.ok) return fail(res.status, { avatarError: m.prof_err_remove() });

		return { avatarSuccess: m.prof_picture_removed() };
	}
};