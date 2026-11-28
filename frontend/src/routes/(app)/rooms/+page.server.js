import { error, fail } from '@sveltejs/kit';
import { timetableApi } from '$lib/server/timetable.js';
import { errorText } from '$lib/server/quiz.js';
import { m } from '$lib/paraglide/messages.js';

// Räume verwalten – nur Admins.
// Räume gehören zum Stundenplan, daher über timetableApi (mit TIMETABLE_MOCK=1 antwortet der Mock)
export async function load({ locals }) {
	if (locals.user.role !== 'admin') error(403, m.rooms_err_admins_only());

	const res = await timetableApi('/rooms', locals);
	// Solange Gridis Endpunkt noch fehlt: leere Liste + Hinweis statt Fehlerseite
	if (res.status === 404) return { rooms: [], missing: true };
	if (!res.ok) error(res.status, await errorText(res, m.rooms_err_load()));

	return { rooms: await res.json(), missing: false };
}

const isAdmin = (locals) => locals.user.role === 'admin';

// Formular -> { name, capacity } prüfen (gemeinsam für Anlegen und Bearbeiten)
function readRoom(form) {
	const name = form.get('name')?.toString().trim() ?? '';
	const cap = form.get('capacity')?.toString().trim() ?? '';

	if (!name) return { error: m.rooms_err_name() };
	if (name.length > 50) return { error: m.tt_err_room_long() };

	const capacity = cap ? Number(cap) : null; // Plätze sind optional
	if (capacity !== null && !(Number.isInteger(capacity) && capacity >= 1 && capacity <= 500)) {
		return { error: m.rooms_err_capacity() };
	}
	return { room: { name, capacity } };
}

export const actions = {
	// Neuer Raum (Name doppelt -> API antwortet 409 mit Text)
	create: async ({ request, locals }) => {
		if (!isAdmin(locals)) return fail(403, { error: m.rooms_err_admins_only() });

		const { room, error } = readRoom(await request.formData());
		if (error) return fail(400, { error });

		const res = await timetableApi('/rooms', locals, { method: 'POST', json: room });
		if (!res.ok) return fail(res.status, { error: await errorText(res, m.rooms_err_save()) });
		return { created: true };
	},

	// Raum umbenennen / Plätze ändern – der Stundenplan zeigt den neuen Namen automatisch (room_id)
	update: async ({ request, locals }) => {
		if (!isAdmin(locals)) return fail(403, { listError: m.rooms_err_admins_only() });
		const form = await request.formData();

		const { room, error } = readRoom(form);
		if (error) return fail(400, { listError: error });

		const res = await timetableApi(`/rooms/${Number(form.get('id'))}`, locals, { method: 'PUT', json: room });
		if (!res.ok) return fail(res.status, { listError: await errorText(res, m.rooms_err_save()) });
		return { updated: true };
	},

	// Raum löschen – wird er noch im Stundenplan verwendet, antwortet die API mit 409
	delete: async ({ request, locals }) => {
		if (!isAdmin(locals)) return fail(403, { listError: m.rooms_err_admins_only() });
		const id = Number((await request.formData()).get('id'));

		const res = await timetableApi(`/rooms/${id}`, locals, { method: 'DELETE' });
		if (!res.ok && res.status !== 404) {
			return fail(res.status, { listError: await errorText(res, m.rooms_err_delete()) });
		}
		return { deleted: true };
	}
};