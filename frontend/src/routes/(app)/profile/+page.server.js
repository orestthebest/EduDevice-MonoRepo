import { fail } from '@sveltejs/kit';
import { api } from '$lib/server/api.js';

// Profilseite: die Daten kommen schon von /auth/me (hooks.server.js -> locals.user),
// deshalb ist hier kein extra API-Aufruf nötig.
export function load({ locals }) {
	const { id, first_name, last_name, username, email, role, profile_image } = locals.user;
	return { profile: { id, first_name, last_name, username, email, role, profile_image } };
}

export const actions = {
	// Eigene E-Mail ändern – die User-ID nimmt die API aus dem JWT
	updateEmail: async ({ request, locals }) => {
		const form = await request.formData();
		// trim() ist Pflicht: Leerzeichen am Rand gibt bei der API 422
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
		if (res.status === 422) return fail(400, { email, error: 'Please enter a valid email address' });
		if (!res.ok) return fail(res.status, { email, error: 'Could not save your email' });

		// Danach lädt SvelteKit die Seite neu -> hooks.server.js holt die neue E-Mail von /auth/me
		return { success: true };
	},

	// Profilbild hochladen – Prüfen, Zuschneiden auf 256x256 und WebP macht die API
	uploadAvatar: async ({ request, locals }) => {
		const form = await request.formData();
		const file = form.get('file');

		if (!(file instanceof File) || file.size === 0) {
			return fail(400, { avatarError: 'Please choose an image' });
		}
		if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
			return fail(400, { avatarError: 'Only JPG, PNG or WebP images are allowed' });
		}
		if (file.size > 2 * 1024 * 1024) {
			return fail(400, { avatarError: 'Image is too big (max. 2 MB)' });
		}

		const body = new FormData();
		body.append('file', file);
		const res = await api('/users/me/avatar', { method: 'POST', token: locals.token, form: body });

		if (res.status === 413) return fail(400, { avatarError: 'Image is too big (max. 2 MB)' });
		if (res.status === 400) return fail(400, { avatarError: 'This file is not a valid image' });
		if (!res.ok) return fail(res.status, { avatarError: 'Upload failed, please try again' });

		return { avatarSuccess: 'Your profile picture has been updated.' };
	},

	// Profilbild entfernen -> wieder Initialen
	removeAvatar: async ({ locals }) => {
		const res = await api('/users/me/avatar', { method: 'DELETE', token: locals.token });
		if (!res.ok) return fail(res.status, { avatarError: 'Could not remove the picture' });

		return { avatarSuccess: 'Your profile picture has been removed.' };
	}
};