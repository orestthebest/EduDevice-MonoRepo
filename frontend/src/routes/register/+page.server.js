import { fail, redirect } from '@sveltejs/kit';
import { api, login } from '$lib/server/api.js';
import { m } from '$lib/paraglide/messages.js';

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
			return fail(400, { values, error: m.error_fill_all() });
		}
		if (password.length < 8) {
			return fail(400, { values, error: m.error_password_short() });
		}
		if (!role) {
			return fail(400, { values, error: m.error_choose_role() });
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
			const error = detail.includes('E-Mail') ? m.error_email_taken() : m.error_username_taken();
			return fail(400, { values, error });
		}
		// 422 = Eingabe ungültig (z. B. Username zu kurz, E-Mail falsch)
		if (res.status === 422) {
			return fail(400, { values, error: m.error_invalid_input() });
		}
		if (!res.ok) {
			return fail(res.status, { values, error: m.error_register_failed() });
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