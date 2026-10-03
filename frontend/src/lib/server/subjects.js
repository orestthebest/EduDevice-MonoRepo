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

// Alle Schüler, die in einem Fach eingetragen sind (mit ihrer Klasse)
export async function getSubjectStudents(classSubjectId) {
	const [rows] = await pool.execute(
		`SELECT u.id, u.first_name, u.last_name, u.username,
		        (SELECT GROUP_CONCAT(c.name SEPARATOR ', ')
		         FROM student_classes sc JOIN classes c ON c.id = sc.class_id
		         WHERE sc.student_id = u.id) AS class_name
		 FROM class_subject_students x
		 JOIN users u ON u.id = x.student_id
		 WHERE x.class_subject_id = ?
		 ORDER BY u.last_name, u.first_name`,
		[classSubjectId]
	);
	return rows;
}

// Alle Schüler, die NOCH NICHT im Fach sind (für "Add student")
export async function getAddableStudents(classSubjectId) {
	const [rows] = await pool.execute(
		`SELECT u.id, u.first_name, u.last_name, u.username
		 FROM users u
		 WHERE u.role = 'schueler'
		   AND u.id NOT IN (SELECT student_id FROM class_subject_students WHERE class_subject_id = ?)
		 ORDER BY u.last_name, u.first_name`,
		[classSubjectId]
	);
	return rows;
}

// Schüler zu einem Fach hinzufügen.
// Das SELECT ... WHERE role = 'schueler' stellt sicher, dass nur echte Schüler eingetragen werden.
// INSERT IGNORE: ist er schon drin, passiert einfach nichts.
export async function addStudent(classSubjectId, studentId) {
	const [result] = await pool.execute(
		`INSERT IGNORE INTO class_subject_students (class_subject_id, student_id)
		 SELECT ?, id FROM users WHERE id = ? AND role = 'schueler'`,
		[classSubjectId, studentId]
	);
	return result.affectedRows > 0;
}

// Schüler aus einem Fach entfernen
export async function removeStudent(classSubjectId, studentId) {
	await pool.execute(
		'DELETE FROM class_subject_students WHERE class_subject_id = ? AND student_id = ?',
		[classSubjectId, studentId]
	);
}

// Material löschen. Gibt den Dateinamen im uploads-Ordner zurück (zum Löschen der Datei),
// oder null, wenn es das Material in diesem Fach nicht gibt.
export async function deleteMaterial(materialId, classSubjectId) {
	const [rows] = await pool.execute(
		'SELECT stored_name FROM materials WHERE id = ? AND class_subject_id = ?',
		[materialId, classSubjectId]
	);
	if (rows.length === 0) return null;

	await pool.execute('DELETE FROM materials WHERE id = ?', [materialId]);
	return rows[0].stored_name;
}

// Fach löschen.
// Noten, Quizzes und Stundenplan hängen OHNE "ON DELETE CASCADE" am Fach bzw. würden
// Anwesenheiten mitlöschen -> dann blockieren wir das Löschen lieber.
// Materialien + Schülerliste werden per CASCADE automatisch mitgelöscht.
// Rückgabe: { blocked: true } oder { storedNames: [...] } (Dateien, die gelöscht werden müssen)
export async function deleteClassSubject(classSubjectId) {
	const [[usage]] = await pool.execute(
		`SELECT
			(SELECT COUNT(*) FROM grades        WHERE class_subject_id = ?) +
			(SELECT COUNT(*) FROM period_grades WHERE class_subject_id = ?) +
			(SELECT COUNT(*) FROM quizzes       WHERE class_subject_id = ?) +
			(SELECT COUNT(*) FROM timetable     WHERE class_subject_id = ?) AS total`,
		[classSubjectId, classSubjectId, classSubjectId, classSubjectId]
	);
	if (Number(usage.total) > 0) return { blocked: true };

	const [files] = await pool.execute(
		'SELECT stored_name FROM materials WHERE class_subject_id = ?',
		[classSubjectId]
	);
	await pool.execute('DELETE FROM class_subjects WHERE id = ?', [classSubjectId]);

	return { storedNames: files.map((f) => f.stored_name) };
}