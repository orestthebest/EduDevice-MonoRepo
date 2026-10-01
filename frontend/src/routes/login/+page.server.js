import { fail, redirect } from '@sveltejs/kit';
import pool from '$lib/server/database.js';
import { verifyPassword, createSession } from '$lib/server/auth.js';

// Wer schon eingeloggt ist, braucht die Login-Seite nicht
export function load({ locals }) {
    if (locals.user) redirect(303, '/');
}

export const actions = {
    // Prüft die Login-Daten und erstellt bei Erfolg eine Session.
    login: async ({ request, cookies }) => {
        const form = await request.formData();
        const username = form.get('username')?.toString().trim();
        const password = form.get('password')?.toString();

        if (!username || !password) {
            return fail(400, { username, error: 'Please fill in all fields' });
        }

        const [rows] = await pool.execute('SELECT * FROM users WHERE username = ?', [username]);

        // Gleiche Fehlermeldung für "User existiert nicht" und "falsches Passwort",
        // damit man nicht herausfinden kann, welche Usernamen es gibt.
        if (rows.length === 0) {
            return fail(400, { username, error: 'Wrong username or password' });
        }

        const valid = await verifyPassword(password, rows[0].password_hash);
        if (!valid) {
            return fail(400, { username, error: 'Wrong username or password' });
        }

        // Session-Cookie setzen (30 Tage gültig) und zur Startseite weiterleiten.
        const sessionId = await createSession(rows[0].id);
        cookies.set('session', sessionId, {
            path: '/',
            maxAge: 60 * 60 * 24 * 30
        });

        redirect(303, '/');
    }
};