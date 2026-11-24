import { error, fail } from '@sveltejs/kit';
import { excuseApi } from '$lib/server/excuses.js';
import { errorText } from '$lib/server/quiz.js';
import { m } from '$lib/paraglide/messages.js';

// Lehrerseite: alle Entschuldigungen der Klassen, in denen ich Klassenvorstand bin
export async function load({ locals }) {
	if (locals.user.role === 'schueler') error(403, m.rev_err_teachers_only());

	const res = await excuseApi('/excuses/class-teacher', locals);
	if (!res.ok) error(res.status, await errorText(res, m.rev_err_load()));
	const excuses = await res.json();

	return {
		pending: excuses.filter((e) => e.status === 'pending'),
		reviewed: excuses.filter((e) => e.status !== 'pending')
	};
}

export const actions = {
	// Annehmen oder ablehnen – welcher Button gedrückt wurde, steht in "status"
	review: async ({ request, locals }) => {
		const form = await request.formData();
		const id = Number(form.get('id'));
		const status = form.get('status')?.toString();
		const comment = form.get('comment')?.toString().trim() ?? '';

		if (!['accepted', 'rejected'].includes(status)) return fail(400, { id, comment, error: m.rev_err_invalid() });
		if (status === 'rejected' && comment.length === 0) {
			return fail(400, { id, comment, error: m.rev_err_comment_required() });
		}
		if (comment.length > 500) return fail(400, { id, comment, error: m.rev_err_comment_long() });

		const res = await excuseApi(`/excuses/${id}`, locals, {
			method: 'PATCH',
			json: { status, teacher_comment: comment || null }
		});

		if (res.status === 409) return fail(409, { id, comment, error: m.exc_err_reviewed() });
		if (res.status === 404) return fail(404, { id, comment, error: m.rev_err_not_your_class() });

		if (!res.ok) return fail(res.status, { id, comment, error: await errorText(res, m.rev_err_save()) });

		return { id, success: status === 'accepted' ? m.rev_accepted_msg() : m.rev_rejected_msg() };
	}
};