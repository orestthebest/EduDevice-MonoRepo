import { error, fail } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { api, apiJson } from '$lib/server/api.js';
import { timetableApi } from '$lib/server/timetable.js';
import { errorText } from '$lib/server/quiz.js';
import { PERIODS, WEEKDAYS } from '$lib/timetable.js';

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


export const actions = {
	// Neue Unterrichtseinheit: Fach + Wochentag + Stunden von–bis + Raum
	create: async ({ request, locals }) => {
		if (locals.user.role !== 'admin') return fail(403, { error: 'Only administrators can manage timetables' });

		const form = await request.formData();
		const class_id = Number(form.get('class_id'));
		const class_subject_id = Number(form.get('class_subject_id'));
		const weekday = form.get('weekday')?.toString() ?? '';
		const period_from = Number(form.get('period_from'));
		const period_to = Number(form.get('period_to'));
		const room = form.get('room')?.toString().trim() ?? '';

		if (!class_subject_id) return fail(400, { error: 'Please choose a subject' });
		if (!WEEKDAYS.some((w) => w.key === weekday)) return fail(400, { error: 'Please choose a weekday' });
		if (!(period_from >= 1 && period_to <= PERIODS.length && period_from <= period_to)) {
			return fail(400, { error: 'The last period must not be before the first one' });
		}
		if (room.length > 50) return fail(400, { error: 'Room name is too long (max. 50 characters)' });

		// Fach muss existieren (Lehrkraft + Klasse braucht außerdem der Mock für seine Prüfungen)
		const subjectRes = await api(`/subjects/${class_subject_id}`, { token: locals.token });
		if (!subjectRes.ok) return fail(400, { error: 'This subject does not exist anymore – please reload the page' });
		const subject = await subjectRes.json();

		const res = await timetableApi('/timetable', locals, {
			method: 'POST',
			json: { class_subject_id, weekday, period_from, period_to, room: room || null },
			mock: { class_id, class_name: subject.class_name, teacher_id: subject.teacher_id, teacher_name: subject.teacher_name }
		});

		if (res.status === 409) return fail(409, { error: await errorText(res, 'This time is already taken') });
		if (!res.ok) return fail(res.status, { error: await errorText(res, 'Could not save the lesson') });
		return { created: true };
	}
};