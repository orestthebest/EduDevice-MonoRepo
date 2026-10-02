import { fail, redirect } from '@sveltejs/kit';
import pool from '$lib/server/database.js';
import { hashPassword, createSession } from '$lib/server/auth.js';

export function load({ locals }) {
    if (locals.user) redirect(303, '/');
}

// Formular-Wert -> Wert in der DB (users.role). Admin kann man sich NICHT selbst geben.
const ROLES = { student: 'schueler', teacher: 'lehrkraft' };


// Legt einen neuen User (Rolle: student) an und loggt ihn direkt ein.
export const actions = {
    register: async ({ request, cookies }) => {
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

        let result;
        try {
            // Passwort wird gehasht gespeichert, niemals im Klartext.
            [result] = await pool.execute(
                'INSERT INTO users (first_name, last_name, username, email, password_hash, role) VALUES (?, ?, ?, ?, ?, ?)',
                [values.firstName, values.lastName, values.username, values.email, await hashPassword(password), role]
            );
        } catch (err) {
            // username und email sind UNIQUE -> Duplikate lösen diesen Fehler aus.
            if (err.code === 'ER_DUP_ENTRY') {
                const error = err.message.includes('email')
                    ? 'E-mail is already registered'
                    : 'Username is already taken';
                return fail(400, { values, error });
            }
            throw err;
        }

        // Session-Cookie setzen (30 Tage gültig) und zur Startseite weiterleiten.
        const sessionId = await createSession(result.insertId);
        cookies.set('session', sessionId, {
            path: '/',
            maxAge: 60 * 60 * 24 * 30
        });

        redirect(303, '/');
    }
};