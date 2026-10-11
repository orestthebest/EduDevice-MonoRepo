// frontend/src/lib/server/api.js
// Ersetzt database.js: die WebApp spricht NICHT mehr direkt mit MySQL,
// sondern nur noch mit der REST-API (Ziel-M-2).
//
// .env am Server:  API_URL=http://127.0.0.1:8000
// Der JWT kommt beim Login von der API und liegt im httpOnly-Cookie "token".
import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';

const API_URL = env.API_URL || 'http://127.0.0.1:8000';

// Allgemeiner Aufruf. token = JWT aus dem Cookie (oder null bei Login/Register)
// clientIp = event.getClientAddress() -> damit das Login-Limit pro Benutzer-IP gilt
export async function api(path, { method = 'GET', token = null, json, form, clientIp } = {}) {
	const headers = {};
	if (clientIp) headers['X-Forwarded-For'] = clientIp;
	if (token) headers.Authorization = `Bearer ${token}`;

	let body;
	if (json !== undefined) {
		headers['Content-Type'] = 'application/json';
		body = JSON.stringify(json);
	} else if (form !== undefined) {
		body = form; // FormData (Upload) oder URLSearchParams (Login)
	}

	const res = await fetch(API_URL + path, { method, headers, body });
	return res;
}

// Wie api(), wirft aber bei Fehlern direkt einen SvelteKit-Fehler und gibt JSON zurück
export async function apiJson(path, options = {}) {
	const res = await api(path, options);
	if (!res.ok) {
		let detail = res.statusText;
		try {
			const data = await res.json();
			detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
		} catch {
			/* keine JSON-Antwort */
		}
		error(res.status, detail);
	}
	return res.json();
}

// Login: liefert { access_token, role, user_id, username, first_name, last_name }
// oder null bei falschen Daten. 429 = zu viele Versuche.
export async function login(username, password, clientIp) {
	const res = await api('/auth/login', {
		method: 'POST',
		clientIp,
		form: new URLSearchParams({ username, password })
	});
	if (res.status === 401) return null;
	if (!res.ok) error(res.status, res.status === 429 ? 'Too many attempts, wait a minute' : 'Login failed');
	return res.json();
}
