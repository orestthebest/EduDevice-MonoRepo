-- ============================================================
-- EduDevice Schema V4.4 (Migration von V4.3) - ENTWURF
-- Quiz-System: Fragen (Multiple Choice, Wahr/Falsch, Lueckentext),
-- Antworten und automatische Bewertung in der API.
-- Basis: Vorschlag von Orest, angepasst an das bestehende Schema:
--   * quizzes und quiz_results gibt es schon (V4.2) -> ALTER statt CREATE
--   * alle IDs INT UNSIGNED (sonst schlagen die Fremdschluessel fehl)
--   * quizzes haengt OHNE CASCADE an class_subjects (schuetzt Ergebnisse)
--   * quiz_results bleibt die "Abgabe" (Jorik's Pipeline liest score),
--     score bleibt INT, neu nur max_score
-- VOR DEM AUSFUEHREN: Backup machen und mit Jorik abklaeren (quiz_results).
-- ============================================================

USE edudevice_db;

-- ---------- quizzes erweitern ----------
ALTER TABLE quizzes
    ADD COLUMN description  TEXT NULL AFTER title,
    ADD COLUMN created_by   INT UNSIGNED NULL AFTER class_subject_id,
    ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT FALSE;

-- bestehende Quizzes: Ersteller = Lehrkraft des Fachs
UPDATE quizzes q
JOIN class_subjects cs ON cs.id = q.class_subject_id
SET q.created_by = cs.teacher_id
WHERE q.created_by IS NULL;

ALTER TABLE quizzes
    MODIFY created_by INT UNSIGNED NOT NULL,
    ADD CONSTRAINT fk_quizzes_created_by FOREIGN KEY (created_by) REFERENCES users(id);

-- ---------- Fragen ----------
CREATE TABLE IF NOT EXISTS quiz_questions (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    quiz_id         INT UNSIGNED NOT NULL,
    position        INT UNSIGNED NOT NULL DEFAULT 0,
    type            ENUM('mc','tf','gap') NOT NULL,      -- Multiple Choice, Wahr/Falsch, Lueckentext
    question_text   TEXT NOT NULL,
    points          INT UNSIGNED NOT NULL DEFAULT 1,
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
    INDEX idx_qq_quiz_pos (quiz_id, position)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Antwortmoeglichkeiten ----------
-- mc:  mehrere Optionen, eine oder mehrere is_correct = TRUE
-- tf:  zwei Optionen "Wahr" / "Falsch"
-- gap: akzeptierte Antworten pro Luecke (gap_index), alle is_correct = TRUE
CREATE TABLE IF NOT EXISTS quiz_options (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    question_id     INT UNSIGNED NOT NULL,
    option_text     VARCHAR(500) NOT NULL,
    is_correct      BOOLEAN NOT NULL DEFAULT FALSE,
    gap_index       TINYINT UNSIGNED NULL,
    position        INT UNSIGNED NOT NULL DEFAULT 0,
    FOREIGN KEY (question_id) REFERENCES quiz_questions(id) ON DELETE CASCADE,
    INDEX idx_qo_question (question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Abgabe: bestehende Tabelle quiz_results ----------
-- score bleibt INT: jede Frage wird ganz oder gar nicht gewertet,
-- Punkte sind ganze Zahlen. Neu nur max_score (erreichbare Punkte).
-- NULL bei alten Abgaben, die vor V4.4 gespeichert wurden.
ALTER TABLE quiz_results
    ADD COLUMN max_score INT UNSIGNED NULL AFTER score;

-- ---------- Einzelne Antworten einer Abgabe ----------
CREATE TABLE IF NOT EXISTS quiz_answers (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    result_id       INT UNSIGNED NOT NULL,               -- = quiz_results.id
    question_id     INT UNSIGNED NOT NULL,
    option_id       INT UNSIGNED NULL,                   -- mc / tf: gewaehlte Option
    gap_index       TINYINT UNSIGNED NULL,               -- gap: welche Luecke
    text_answer     VARCHAR(500) NULL,                   -- gap: eingegebener Text
    is_correct      BOOLEAN NOT NULL,
    FOREIGN KEY (result_id)   REFERENCES quiz_results(id)   ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES quiz_questions(id) ON DELETE CASCADE,
    FOREIGN KEY (option_id)   REFERENCES quiz_options(id)   ON DELETE SET NULL,
    INDEX idx_qa_result (result_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
