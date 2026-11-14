import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { apiJson } from '$lib/server/api.js';
import { timetableApi } from '$lib/server/timetable.js';
import { errorText } from '$lib/server/quiz.js';

// Stundenplan verwalten (M-4) – nur Admins. ?class=3 -> Stundenplan dieser Klasse
export async function load({ locals, url }) {
	if (locals.user.role !== 'admin') error(403, 'Only administrators can manage timetables');

	const token = locals.token;
	const [classes, allSubjects] = await Promise.all([
		apiJson('/classes', { token }),
		apiJson('/subjects', { token })
	]);
	const mock = env.TIMETABLE_MOCK === '1';
	if (classes.length === 0) return { classes, schoolClass: null, subjects: [], slots: [], mock };

	const schoolClass = classes.find((c) => c.id === Number(url.searchParams.get('class'))) ?? classes[0];

	const res = await timetableApi(`/timetable/class/${schoolClass.id}`, locals);
	if (!res.ok) error(res.status, await errorText(res, 'Could not load the timetable'));

	return {
		classes,
		schoolClass,
		// Fächer dieser Klasse (class_subjects) – für Namen im Raster und später für den Dialog
		subjects: allSubjects.filter((s) => s.class_name === schoolClass.name),
		slots: await res.json(),
		mock
	};
}