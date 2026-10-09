import pool from '$lib/server/database.js';

// Eine Klasse laden (mit Schuljahr)
export async function getClass(classId) {
	const [rows] = await pool.execute(
		`SELECT c.id, c.name, c.school_year_id, sy.label AS school_year
		 FROM classes c JOIN school_years sy ON sy.id = c.school_year_id
		 WHERE c.id = ?`,
		[classId]
	);
	return rows[0] ?? null;
}

// Alle Schüler einer Klasse
export async function getClassStudents(classId) {
	const [rows] = await pool.execute(
		`SELECT u.id, u.first_name, u.last_name, u.username
		 FROM student_classes sc JOIN users u ON u.id = sc.student_id
		 WHERE sc.class_id = ?
		 ORDER BY u.last_name, u.first_name`,
		[classId]
	);
	return rows;
}

// Schüler, die man zuweisen kann:
// alle Schüler, die in diesem Schuljahr noch in KEINER Klasse sind
export async function getAssignableStudents(schoolYearId) {
	const [rows] = await pool.execute(
		`SELECT u.id, u.first_name, u.last_name, u.username
		 FROM users u
		 WHERE u.role = 'schueler'
		   AND NOT EXISTS (
		     SELECT 1 FROM student_classes sc
		     JOIN classes c ON c.id = sc.class_id
		     WHERE sc.student_id = u.id AND c.school_year_id = ?
		   )
		 ORDER BY u.last_name, u.first_name`,
		[schoolYearId]
	);
	return rows;
}

// Schüler einer Klasse zuweisen + in alle Fächer der Klasse eintragen.
// Transaktion: entweder beides klappt oder nichts wird gespeichert.
export async function addStudentToClass(classId, studentId) {
	const conn = await pool.getConnection();
	try {
		await conn.beginTransaction();

		await conn.execute(
			`INSERT INTO student_classes (student_id, class_id)
			 SELECT id, ? FROM users WHERE id = ? AND role = 'schueler'`,
			[classId, studentId]
		);

		await conn.execute(
			`INSERT IGNORE INTO class_subject_students (class_subject_id, student_id)
			 SELECT cs.id, ? FROM class_subjects cs WHERE cs.class_id = ?`,
			[studentId, classId]
		);

		await conn.commit();
	} catch (err) {
		await conn.rollback();
		throw err;
	} finally {
		conn.release();
	}
}

// Schüler aus der Klasse entfernen + aus allen Fächern dieser Klasse
export async function removeStudentFromClass(classId, studentId) {
	const conn = await pool.getConnection();
	try {
		await conn.beginTransaction();

		await conn.execute(
			`DELETE x FROM class_subject_students x
			 JOIN class_subjects cs ON cs.id = x.class_subject_id
			 WHERE cs.class_id = ? AND x.student_id = ?`,
			[classId, studentId]
		);

		await conn.execute(
			'DELETE FROM student_classes WHERE class_id = ? AND student_id = ?',
			[classId, studentId]
		);

		await conn.commit();
	} catch (err) {
		await conn.rollback();
		throw err;
	} finally {
		conn.release();
	}
}