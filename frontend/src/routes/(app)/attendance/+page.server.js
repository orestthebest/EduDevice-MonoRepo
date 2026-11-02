import { error, fail } from '@sveltejs/kit';
import { api, apiJson } from '$lib/server/api.js';
import { errorText } from '$lib/server/quiz.js';

// Heute als "YYYY-MM-DD" (lokale Zeit, nicht UTC)
function today() {
	const d = new Date();
	return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// Lehrerseite: Anwesenheit pro Stunde erfassen (Vertrag: backend/docs/API_FUER_OREST.md, V2.8)
// Auswahl steht in der URL: ?subject=<class_subject_id>&date=YYYY-MM-DD&time=HH:MM
export async function load({ locals, url }) {
	if (locals.user.role === 'schueler') error(403, 'Only teachers can take attendance');
	const token = locals.token;

	// Lehrer sehen nur ihre eigenen Fächer, Admin alle
	let subjects = await apiJson('/subjects', { token });
	if (locals.user.role === 'lehrkraft') subjects = subjects.filter((s) => s.teacher_id === locals.user.id);

	const subjectId = Number(url.searchParams.get('subject')) || subjects[0]?.id || null;
	const date = url.searchParams.get('date') || today();
	let time = url.searchParams.get('time') || '';

	if (!subjectId) {
		return { subjects, subjectId, date, time, slots: [], slotError: null, lesson: null, history: [] };
	}

	const q = `class_subject_id=${subjectId}`;
	const [slotsRes, history] = await Promise.all([
		api(`/attendance/slots?${q}&date=${date}`, { token }),
		apiJson(`/attendance/history?${q}`, { token })
	]);

	// 400 = Wochenende -> Meldung statt Fehlerseite
	const slots = slotsRes.ok ? await slotsRes.json() : [];
	const slotError = slotsRes.ok ? null : await errorText(slotsRes, 'Could not load the timetable');

	// Keine oder ungültige Uhrzeit gewählt -> erste Stunde des Tages laut Stundenplan
	if (!slots.some((s) => s.start_time.slice(0, 5) === time)) time = slots[0]?.start_time.slice(0, 5) ?? '';

	// Alle Schüler des Fachs mit ihrem Status (status null = noch nicht erfasst)
	const lesson = time ? await apiJson(`/attendance?${q}&date=${date}&start_time=${time}`, { token }) : null;

	return { subjects, subjectId, date, time, slots, slotError, lesson, history };
}

export const actions = {
	// Anwesenheit einer Stunde speichern (neu anlegen oder korrigieren)
	save: async ({ request, locals }) => {
		const form = await request.formData();
		const class_subject_id = Number(form.get('class_subject_id'));
		const date = form.get('date')?.toString();
		const start_time = form.get('start_time')?.toString();

		// pro Schüler: <input name="student_id"> + <input name="status-<id>">
		const entries = form.getAll('student_id').map((id) => ({
			student_id: Number(id),
			status: form.get(`status-${id}`)?.toString()
		}));

		if (entries.length === 0) return fail(400, { error: 'There are no students in this subject' });
		if (entries.some((e) => !['anwesend', 'abwesend', 'verspaetet'].includes(e.status))) {
			return fail(400, { error: 'Invalid attendance status' });
		}

		const res = await api('/attendance', {
			method: 'PUT',
			token: locals.token,
			json: { class_subject_id, date, start_time, entries }
		});
		if (!res.ok) return fail(res.status, { error: await errorText(res, 'Could not save attendance') });

		return { success: 'Attendance saved.' };
	}
};