import { error } from '@sveltejs/kit';
import { getClasses } from '$lib/server/subjects.js';

// Klassenübersicht – nur für Admins
export async function load({ locals }) {
	if (locals.user.role !== 'admin') error(403, 'Only administrators can manage classes');
	return { classes: await getClasses() };
}