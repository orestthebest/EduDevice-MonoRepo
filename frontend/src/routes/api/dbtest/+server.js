import { json } from '@sveltejs/kit';
import { db } from '$lib/server/database';

export async function GET() {
  const [rows] = await db.query('SELECT id, username, role FROM users LIMIT 5');
  return json(rows);
}