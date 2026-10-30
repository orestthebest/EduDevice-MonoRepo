-- ============================================================
-- EduDevice Schema V4.6 (Migration von V4.5)
-- Entschuldigungssystem (O-3, Vorschlag von Orest, 29.10.2026)
-- Die Tabelle excuses und attendance.excuse_id gibt es schon seit V4.2.
-- Neu:
--   classes.class_teacher_id   Klassenvorstand, prueft die Entschuldigungen
--   excuses.teacher_comment    Kommentar des Klassenvorstands
--   excuses.reviewed_by / _at  wer hat wann angenommen/abgelehnt
-- Alle IDs INT UNSIGNED wie im restlichen Schema.
-- VOR DEM AUSFUEHREN: Backup machen.
-- ============================================================

USE edudevice_db;

ALTER TABLE classes
    ADD COLUMN class_teacher_id INT UNSIGNED NULL AFTER name,
    ADD CONSTRAINT fk_classes_class_teacher
        FOREIGN KEY (class_teacher_id) REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE excuses
    ADD COLUMN teacher_comment TEXT NULL AFTER status,
    ADD COLUMN reviewed_by     INT UNSIGNED NULL AFTER teacher_comment,
    ADD COLUMN reviewed_at     DATETIME NULL AFTER reviewed_by,
    ADD CONSTRAINT fk_excuses_reviewed_by
        FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    ADD INDEX idx_excuses_student (student_id, submitted_at);
