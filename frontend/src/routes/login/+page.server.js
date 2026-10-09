import { fail, redirect } from '@sveltejs/kit';
import pool from '$lib/server/database.js';
import { verifyPassword, createSession } from '$lib/server/auth.js';

// Wer schon eingeloggt ist, braucht die Login-Seite nicht
export function load({ locals }) {
    if (locals.user) redirect(303, '/');
}
// Formular-Wert -> Wert in der DB (users.role)
const ROLES = { student: 'schueler', teacher: 'lehrkraft', admin: 'admin' };
export const actions = {
    // Prüft die Login-Daten und erstellt bei Erfolg eine Session.
    login: async ({ request, cookies, url }) => {
        const form = await request.formData();
        const username = form.get('username')?.toString().trim();
        const password = form.get('password')?.toString();
        const role = ROLES[form.get('role')?.toString()];

        if (!username || !password || !role) {
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
        
        // Gewählte Rolle muss zur Rolle in der DB passen
        if (rows[0].role !== role) {
            return fail(400, { username, error: 'This account does not have the selected role' });
        }

        // Session-Cookie setzen (30 Tage gültig) und zur Startseite weiterleiten.
        const sessionId = await createSession(rows[0].id);
        cookies.set('session', sessionId, {
            path: '/',
            maxAge: 60 * 60 * 24 * 30,
            secure: url.protocol === 'https:'
        });

        redirect(303, '/');
    }
};