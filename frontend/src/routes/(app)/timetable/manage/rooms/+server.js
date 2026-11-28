import { error, json } from '@sveltejs/kit';
import { timetableApi } from '$lib/server/timetable.js';
import { m } from '$lib/paraglide/messages.js';

// Räume für den Stundenplan-Dialog, belegte mit taken_by = Klasse:
// /timetable/manage/rooms?weekday=Di&period_from=3&period_to=4&ignore=12,13
// Antwort: [{ id, name, capacity, taken_by }] – oder null, solange die API das noch nicht kann
// (dann zeigt der Dialog weiter das Textfeld)
export async function GET({ url, locals }) {
	if (!locals.user) error(401, m.err_login());
	if (locals.user.role !== 'admin') error(403, m.rooms_err_admins_only());

	const params = new URLSearchParams();
	for (const key of ['weekday', 'period_from', 'period_to', 'ignore']) {
		const value = url.searchParams.get(key);
		if (value) params.set(key, value);
	}

	const res = await timetableApi(`/rooms/availability?${params}`, locals);
	// 404/405/422 = Endpunkt gibt es bei der API noch nicht
	if ([404, 405, 422].includes(res.status)) return json(null);
	if (!res.ok) error(res.status, m.rooms_err_load());
	return json(await res.json());
}