import { error } from '@sveltejs/kit';
import { apiJson } from '$lib/server/api.js';
import { m } from '$lib/paraglide/messages.js';

// Klassenübersicht – nur für Admins
export async function load({ locals }) {
	if (locals.user.role !== 'admin') error(403, m.cls_err_admins_only());
	return { classes: await apiJson('/classes', { token: locals.token }) };
}