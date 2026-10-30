import { error, fail } from '@sveltejs/kit';
import { excuseApi } from '$lib/server/excuses.js';
import { errorText } from '$lib/server/quiz.js';

// Lehrerseite: alle Entschuldigungen der Klassen, in denen ich Klassenvorstand bin
export async function load({ locals }) {
	if (locals.user.role === 'schueler') error(403, 'Only teachers can review excuses');

	const res = await excuseApi('/excuses/class-teacher', locals);
	if (!res.ok) error(res.status, await errorText(res, 'Could not load excuses'));
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

		if (!['accepted', 'rejected'].includes(status)) return fail(400, { id, comment, error: 'Invalid action' });
		if (status === 'rejected' && comment.length === 0) {
			return fail(400, { id, comment, error: 'Please add a comment explaining the rejection' });
		}
		if (comment.length > 500) return fail(400, { id, comment, error: 'Comment is too long (max. 500 characters)' });

		const res = await excuseApi(`/excuses/${id}`, locals, {
			method: 'PATCH',
			json: { status, teacher_comment: comment || null }
		});

		if (res.status === 400) {
		return fail(400, { reason, error: 'One of the selected lessons is already excused – please reload the page' });
		}

		if (res.status === 409) return fail(409, { id, comment, error: 'This excuse has already been reviewed' });
		if (res.status === 404) return fail(404, { id, comment, error: 'This excuse is not from a student of your class' });

		if (!res.ok) return fail(res.status, { id, comment, error: await errorText(res, 'Could not save your decision') });

		return { id, success: status === 'accepted' ? 'Excuse accepted.' : 'Excuse rejected.' };
	}
};