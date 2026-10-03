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

// Alle Klassen (für das Dropdown im "New subject"-Dialog)
export async function getClasses() {
	const [rows] = await pool.execute(
		`SELECT c.id, c.name, sy.label AS school_year
		 FROM classes c JOIN school_years sy ON sy.id = c.school_year_id
		 ORDER BY sy.start_date DESC, c.name`
	);
	return rows;
}

// Alle Fachnamen im Katalog (als Vorschläge beim Tippen)
export async function getSubjectNames() {
	const [rows] = await pool.execute('SELECT name FROM subjects ORDER BY name');
	return rows.map((r) => r.name);
}

// Neues Fach für eine Klasse anlegen.
// 1. Fachname im Katalog suchen oder neu anlegen
// 2. class_subjects-Eintrag (Klasse + Fach + Lehrer) anlegen
// 3. alle Schüler der Klasse automatisch eintragen
// Alles in einer Transaktion: entweder alles klappt oder nichts wird gespeichert.
export async function createClassSubject(teacherId, classId, subjectName) {
	const conn = await pool.getConnection();
	try {
		await conn.beginTransaction();

		// LAST_INSERT_ID(id) sorgt dafür, dass insertId auch bei einem schon
		// vorhandenen Fach die richtige id zurückgibt
		const [subject] = await conn.execute(
			'INSERT INTO subjects (name) VALUES (?) ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)',
			[subjectName]
		);

		const [cs] = await conn.execute(
			'INSERT INTO class_subjects (class_id, subject_id, teacher_id) VALUES (?, ?, ?)',
			[classId, subject.insertId, teacherId]
		);

		await conn.execute(
			`INSERT INTO class_subject_students (class_subject_id, student_id)
			 SELECT ?, sc.student_id
			 FROM student_classes sc
			 JOIN users u ON u.id = sc.student_id AND u.role = 'schueler'
			 WHERE sc.class_id = ?`,
			[cs.insertId, classId]
		);

		await conn.commit();
		return cs.insertId;
	} catch (err) {
		await conn.rollback();
		throw err;
	} finally {
		conn.release();
	}
}

// Ein Fach laden, aber NUR wenn der User Zugriff hat (sonst null)
export async function getClassSubjectForUser(id, user) {
	const f = roleFilter(user);
	const where = f.where ? f.where + ' AND cs.id = ?' : ' WHERE cs.id = ?';
	const [rows] = await pool.execute(SUBJECT_SELECT + f.join + where, [...f.params, id]);
	return rows[0] ?? null;
}

// Alle Materialien eines Fachs (neueste zuerst)
export async function getMaterials(classSubjectId) {
	const [rows] = await pool.execute(
		`SELECT m.id, m.title, m.original_name, m.size_bytes, m.uploaded_at,
		        LOWER(SUBSTRING_INDEX(m.original_name, '.', -1)) AS ext
		 FROM materials m WHERE m.class_subject_id = ? ORDER BY m.uploaded_at DESC`,
		[classSubjectId]
	);
	return rows;
}

// Ein Material laden (für Download), aber NUR wenn der User Zugriff auf das Fach hat
export async function getMaterialForUser(id, user) {
	const [rows] = await pool.execute(
		'SELECT id, class_subject_id, original_name, stored_name, mime_type FROM materials WHERE id = ?',
		[id]
	);
	const material = rows[0];
	if (!material) return null;

	const subject = await getClassSubjectForUser(material.class_subject_id, user);
	return subject ? material : null;
}

// Neues Material in der DB speichern (die Datei selbst liegt schon im uploads-Ordner)
export async function insertMaterial({ classSubjectId, uploadedBy, title, originalName, storedName, mimeType, sizeBytes }) {
	const [result] = await pool.execute(
		`INSERT INTO materials (class_subject_id, uploaded_by, title, original_name, stored_name, mime_type, size_bytes)
		 VALUES (?, ?, ?, ?, ?, ?, ?)`,
		[classSubjectId, uploadedBy, title, originalName, storedName, mimeType, sizeBytes]
	);
	return result.insertId;
}