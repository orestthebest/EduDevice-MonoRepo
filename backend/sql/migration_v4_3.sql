-- ============================================================
-- EduDevice Schema V4.3  (Migration von V4.2)
-- Neu: materials + class_subject_students
-- Grund: Die WebApp (Orest) braucht Lernmaterialien und eine
--        SchuelerInnen-Liste pro Fach. Der Zugriff laeuft ueber die REST-API.
-- "IF NOT EXISTS": falls die Tabellen schon existieren, passiert nichts.
-- Stand 12.10.2026: entspricht 1:1 den Tabellen auf dem Server (von Orest angelegt).
-- ============================================================

USE edudevice_db;

-- Welche SchuelerInnen sind in welchem Fach (class_subject) eingetragen
CREATE TABLE IF NOT EXISTS class_subject_students (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    class_subject_id    INT UNSIGNED NOT NULL,
    student_id          INT UNSIGNED NOT NULL,
    added_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_cs_student (class_subject_id, student_id),
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id)       REFERENCES users(id)          ON DELETE CASCADE
) ENGINE=InnoDB;

-- Lernmaterialien: die Datei liegt in /srv/edudevice/uploads,
-- in der Datenbank stehen nur die Metadaten
CREATE TABLE IF NOT EXISTS materials (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    class_subject_id    INT UNSIGNED NOT NULL,
    uploaded_by         INT UNSIGNED NOT NULL,
    title               VARCHAR(150) NOT NULL,
    original_name       VARCHAR(255) NOT NULL,       -- z. B. "SQL Joins.pdf"
    stored_name         VARCHAR(100) NOT NULL UNIQUE, -- UUID-Name im Upload-Ordner
    mime_type           VARCHAR(100) NOT NULL,
    size_bytes          INT UNSIGNED NOT NULL,
    uploaded_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by)      REFERENCES users(id),           -- kein CASCADE: Lehrkraft loeschen darf Material nicht loeschen
    INDEX idx_materials_cs_date (class_subject_id, uploaded_at)   -- Liste pro Fach, neueste zuerst
) ENGINE=InnoDB;

-- Bestehende SchuelerInnen automatisch in die Faecher ihrer Klasse eintragen.
-- NUR bei einer neuen Datenbank ausfuehren! Auf einer laufenden DB wuerde es
-- SchuelerInnen wieder eintragen, die eine Lehrkraft absichtlich entfernt hat.
INSERT IGNORE INTO class_subject_students (class_subject_id, student_id)
SELECT cs.id, sc.student_id
FROM class_subjects cs
JOIN student_classes sc ON sc.class_id = cs.class_id
JOIN users u ON u.id = sc.student_id AND u.role = 'schueler';
