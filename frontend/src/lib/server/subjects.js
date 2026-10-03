import pool from '$lib/server/database.js';

// Basis-Abfrage: ein Fach (= class_subject) mit Fachname, Klasse, Lehrer,
// Anzahl Dateien und Anzahl Schüler
const SUBJECT_SELECT = `
	SELECT cs.id, cs.teacher_id,
	       s.name AS subject_name,
	       c.name AS class_name,
	       CONCAT(t.first_name, ' ', t.last_name) AS teacher_name,
	       (SELECT COUNT(*) FROM materials m WHERE m.class_subject_id = cs.id) AS file_count,
	       (SELECT COUNT(*) FROM class_subject_students x WHERE x.class_subject_id = cs.id) AS student_count
	FROM class_subjects cs
	JOIN subjects s ON s.id = cs.subject_id
	JOIN classes  c ON c.id = cs.class_id
	JOIN users    t ON t.id = cs.teacher_id`;

// Filter je nach Rolle:
// Schüler -> nur Fächer, in denen er eingetragen ist
// Lehrer  -> nur seine eigenen Fächer
// Admin   -> alle
function roleFilter(user) {
	if (user.role === 'schueler') {
		return {
			join: ' JOIN class_subject_students me ON me.class_subject_id = cs.id AND me.student_id = ?',
			where: '',
			params: [user.id]
		};
	}
	if (user.role === 'lehrkraft') {
		return { join: '', where: ' WHERE cs.teacher_id = ?', params: [user.id] };
	}
	return { join: '', where: '', params: [] };
}

// Alle Fächer, die der User sehen darf
export async function getSubjectsForUser(user) {
	const f = roleFilter(user);
	const [rows] = await pool.execute(
		SUBJECT_SELECT + f.join + f.where + ' ORDER BY c.name, s.name',
		f.params
	);
	return rows;
}

// Die neuesten Materialien aus den Fächern des Users (für das Dashboard)
export async function getRecentMaterials(user, limit = 6) {
	const f = roleFilter(user);
	const [rows] = await pool.execute(
		`SELECT m.id, m.title, m.uploaded_at,
		        s.name AS subject_name,
		        LOWER(SUBSTRING_INDEX(m.original_name, '.', -1)) AS ext
		 FROM materials m
		 JOIN class_subjects cs ON cs.id = m.class_subject_id
		 JOIN subjects s ON s.id = cs.subject_id` +
			f.join + f.where +
			` ORDER BY m.uploaded_at DESC LIMIT ${Number(limit)}`,
		f.params
	);
	return rows;
}