import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { timetableApi } from '$lib/server/timetable.js';
import { errorText } from '$lib/server/quiz.js';
import { todayISO } from '$lib/format.js';
import { weekStart } from '$lib/timetable.js';

// Stundenplan (M-3): Woche des Schülers bzw. der Lehrkraft. ?week=2026-11-16 -> diese Woche
export async function load({ locals, url }) {
	if (locals.user.role === 'admin') error(403, 'Only students and teachers have a timetable');

	const week = url.searchParams.get('week') ?? '';
	const monday = weekStart(/^\d{4}-\d{2}-\d{2}$/.test(week) ? week : todayISO());

	const res = await timetableApi(`/timetable/week?user_id=${locals.user.id}&date=${monday}`, locals);
	if (!res.ok) error(res.status, await errorText(res, 'Could not load your timetable'));

	return {
		monday,
		role: locals.user.role,
		timetable: await res.json(),
		mock: env.TIMETABLE_MOCK === '1'
	};
}