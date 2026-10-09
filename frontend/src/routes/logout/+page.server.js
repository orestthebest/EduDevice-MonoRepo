import { redirect } from '@sveltejs/kit';
import { invalidateSession } from '$lib/server/auth.js';

export function load() {
    redirect(303, '/');
}

export const actions = {
    // Loggt den User aus: löscht die Session in der DB und das Cookie.
    logout: async ({ cookies, url }) => {
        const sessionId = cookies.get('session');

        if (sessionId) {
            await invalidateSession(sessionId);
            cookies.delete('session', { path: '/', secure: url.protocol === 'https:' });
        }

        redirect(303, '/');
    }
};