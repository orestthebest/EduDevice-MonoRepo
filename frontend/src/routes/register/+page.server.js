import { fail, redirect } from '@sveltejs/kit';
import { api, login } from '$lib/server/api.js';

export function load({ locals }) {
	if (locals.user) redirect(303, '/');
}

// Formular-Wert -> Rolle in der DB. Admin kann man sich NICHT selbst geben.
const ROLES = { student: 'schueler', teacher: 'lehrkraft' };

export const actions = {
	// Neuen User über die REST-API anlegen (POST /auth/register) und danach direkt einloggen.
	register: async ({ request, cookies, url, getClientAddress }) => {
		const form = await request.formData();
		const values = {
			firstName: form.get('firstName')?.toString().trim(),
			lastName: form.get('lastName')?.toString().trim(),
			username: form.get('username')?.toString().trim(),
			email: form.get('email')?.toString().trim()
		};
		const password = form.get('password')?.toString();
		const role = ROLES[form.get('role')?.toString()];

		if (!values.firstName || !values.lastName || !values.username || !values.email || !password) {
			return fail(400, { values, error: 'Please fill in all fields' });
		}
		if (password.length < 8) {
			return fail(400, { values, error: 'Password must be at least 8 characters' });
		}
		if (!role) {
			return fail(400, { values, error: 'Please choose Student or Teacher' });
		}

		const res = await api('/auth/register', {
			method: 'POST',
			clientIp: getClientAddress(),
			json: {
				first_name: values.firstName,
				last_name: values.lastName,
				username: values.username,
				email: values.email,
				password,
				role
			}
		});

		// 409 = username oder email existiert schon
		if (res.status === 409) {
			const { detail } = await res.json();
			const error = detail.includes('E-Mail') ? 'E-mail is already registered' : 'Username is already taken';
			return fail(400, { values, error });
		}
		// 422 = Eingabe ungültig (z. B. Username zu kurz, E-Mail falsch)
		if (res.status === 422) {
			return fail(400, { values, error: 'Please check your input (username min. 3 characters, valid e-mail)' });
		}
		if (!res.ok) {
			return fail(res.status, { values, error: 'Registration failed, please try again' });
		}

		// Direkt einloggen und Token-Cookie setzen
		const result = await login(values.username, password, getClientAddress());
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