-- ============================================================
-- EduDevice Schema V4.9 (Migration von V4.8)
-- Anhaenge zu Entschuldigungen (z. B. Arztbestaetigung), Wunsch von Orest 09.11.2026
--   Datei liegt in <UPLOAD_DIR>/excuses/<stored_name>, hier nur die Metadaten.
--   Wird eine Entschuldigung geloescht, fallen ihre Anhaenge mit (CASCADE).
-- Achtung Datenschutz: Arztbestaetigungen sind Gesundheitsdaten.
-- VOR DEM AUSFUEHREN: Backup machen.
-- ============================================================

USE edudevice_db;

CREATE TABLE IF NOT EXISTS excuse_attachments (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    excuse_id       INT UNSIGNED NOT NULL,
    original_name   VARCHAR(255) NOT NULL,
    stored_name     VARCHAR(100) NOT NULL,                 -- UUID + Endung, nie der Originalname
    mime_type       VARCHAR(100) NOT NULL,
    size_bytes      INT UNSIGNED NOT NULL,
    uploaded_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (size_bytes > 0),
    UNIQUE KEY uq_excuse_att_stored (stored_name),
    FOREIGN KEY (excuse_id) REFERENCES excuses(id) ON DELETE CASCADE,
    INDEX idx_excuse_att_excuse (excuse_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
