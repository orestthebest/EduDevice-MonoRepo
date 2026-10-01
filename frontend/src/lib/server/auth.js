import pool from './database.js';
import bcrypt from 'bcrypt';
import { randomUUID } from 'crypto';

// Verschlüsselt ein Passwort zu einem Hash
export async function hashPassword(password) {
    return bcrypt.hash(password, 10);
}

// Vergleicht ein eingegebenes Passwort mit dem gespeicherten Hash.
export async function verifyPassword(password, hash) {
    return bcrypt.compare(password, hash);
}

// Erstellt eine neue Session für einen User und speichert sie in der Datenbank
export async function createSession(userId) {
    const sessionId = randomUUID();
    const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 Tage
    await pool.execute(
        'INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)',
        [sessionId, userId, expiresAt]
    );
    return sessionId;
}

// Prüft eine Session und gibt den dazugehörigen User zurück (oder null).
export async function validateSession(sessionId) {
    const [rows] = await pool.execute(
        `SELECT u.id, u.username, u.first_name, u.last_name, u.email, u.role
         FROM sessions s
         JOIN users u ON s.user_id = u.id
         WHERE s.id = ? AND s.expires_at > NOW()`,
        [sessionId]
    );
    return rows[0] ?? null;
}

// Löscht eine Session aus der Datenbank (Logout).
export async function invalidateSession(sessionId) {
    await pool.execute('DELETE FROM sessions WHERE id = ?', [sessionId]);
}