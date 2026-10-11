import { redirect } from '@sveltejs/kit';

export function load() {
	redirect(303, '/');
}

export const actions = {
	// JWT ist "zustandslos": Die API speichert keine Sessions.
	// Ausloggen = Token-Cookie löschen.
	logout: async ({ cookies, url }) => {
		cookies.delete('token', { path: '/', secure: url.protocol === 'https:' });
		redirect(303, '/');
	}
};