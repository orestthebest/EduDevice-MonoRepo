import { error } from '@sveltejs/kit';
import { apiJson } from '$lib/server/api.js';

// Klassenübersicht – nur für Admins
export async function load({ locals }) {
	if (locals.user.role !== 'admin') error(403, 'Only administrators can manage classes');
	return { classes: await apiJson('/classes', { token: locals.token }) };
}