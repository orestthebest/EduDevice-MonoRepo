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


const isAdmin = (locals) => locals.user.role === 'admin';

function parseJson(value, fallback) {
	try {
		return JSON.parse(value?.toString() ?? '');
	} catch {
		return fallback;
	}
}

// Formular -> Unterrichtseinheit prüfen (gemeinsam für Anlegen und Bearbeiten)
function readLesson(form) {
	const lesson = {
		class_subject_id: Number(form.get('class_subject_id')),
		weekday: form.get('weekday')?.toString() ?? '',
		period_from: Number(form.get('period_from')),
		period_to: Number(form.get('period_to')),
		room: form.get('room')?.toString().trim() || null
	};
	if (!lesson.class_subject_id) return { error: 'Please choose a subject' };
	if (!WEEKDAYS.some((w) => w.key === lesson.weekday)) return { error: 'Please choose a weekday' };
	if (!(lesson.period_from >= 1 && lesson.period_to <= PERIODS.length && lesson.period_from <= lesson.period_to)) {
		return { error: 'The last period must not be before the first one' };
	}
	if (lesson.room && lesson.room.length > 50) return { error: 'Room name is too long (max. 50 characters)' };
	return { lesson };
}

// Unterrichtseinheit anlegen (die API legt eine Zeile pro Stunde an und prüft Überschneidungen)
async function createLesson(locals, classId, lesson) {
	const subjectRes = await api(`/subjects/${lesson.class_subject_id}`, { token: locals.token });
	if (!subjectRes.ok) return { status: 400, error: 'This subject does not exist anymore – please reload the page' };
	const subject = await subjectRes.json();

	const res = await timetableApi('/timetable', locals, {
		method: 'POST',
		json: lesson,
		// nur für den Mock – die echte API kennt Klasse und Lehrkraft selbst
		mock: { class_id: classId, class_name: subject.class_name, teacher_id: subject.teacher_id, teacher_name: subject.teacher_name }
	});
	if (res.ok) return { ok: true };
	return { status: res.status, error: await errorText(res, res.status === 409 ? 'This time is already taken' : 'Could not save the lesson') };
}

// Alle Stunden eines Blocks löschen (404 = schon weg, zählt als erledigt)
async function deleteSlots(locals, ids) {
	for (const id of ids) {
		const res = await timetableApi(`/timetable/${Number(id)}`, locals, { method: 'DELETE' });
		if (!res.ok && res.status !== 404) return { status: res.status, error: await errorText(res, 'Could not delete the lesson') };
	}
	return { ok: true };
}

export const actions = {
	// Neue Unterrichtseinheit: Fach + Wochentag + Stunden von–bis + Raum
	create: async ({ request, locals }) => {
		if (!isAdmin(locals)) return fail(403, { error: 'Only administrators can manage timetables' });
		const form = await request.formData();

		const { lesson, error } = readLesson(form);
		if (error) return fail(400, { error });

		const created = await createLesson(locals, Number(form.get('class_id')), lesson);
		if (!created.ok) return fail(created.status, { error: created.error });
		return { created: true };
	},

	// Block bearbeiten: alte Stunden löschen, neue anlegen.
	// Ist die neue Zeit belegt, wird der alte Block wiederhergestellt – es geht nichts verloren.
	update: async ({ request, locals }) => {
		if (!isAdmin(locals)) return fail(403, { error: 'Only administrators can manage timetables' });
		const form = await request.formData();
		const classId = Number(form.get('class_id'));

		const { lesson, error } = readLesson(form);
		if (error) return fail(400, { error });

		const old = parseJson(form.get('old'), null); // { ids, class_subject_id, weekday, period_from, period_to, room }
		if (!old?.ids?.length) return fail(400, { error: 'Lesson not found – please reload the page' });

		const removed = await deleteSlots(locals, old.ids);
		if (!removed.ok) return fail(removed.status, { error: removed.error });

		const created = await createLesson(locals, classId, lesson);
		if (!created.ok) {
			const { ids, ...previous } = old;
			await createLesson(locals, classId, previous);
			return fail(created.status, { error: created.error });
		}
		return { updated: true };
	},

	// Ganzen Block löschen
	delete: async ({ request, locals }) => {
		if (!isAdmin(locals)) return fail(403, { error: 'Only administrators can manage timetables' });
		const form = await request.formData();

		const old = parseJson(form.get('old'), null);
		if (!old?.ids?.length) return fail(400, { error: 'Lesson not found – please reload the page' });

		const removed = await deleteSlots(locals, old.ids);
		if (!removed.ok) return fail(removed.status, { error: removed.error });
		return { deleted: true };
	}
};