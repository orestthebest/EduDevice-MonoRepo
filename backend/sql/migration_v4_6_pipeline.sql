-- ============================================================
-- EduDevice Schema V4.6 (Migration von V4.5)
-- Tabellen fuer Joriks Prognose-Modell:
--   pipeline_runs   ein Eintrag pro Lauf der Pipeline
--   grade_forecasts vorhergesagte Note pro SchuelerIn, Fach und Trimester
-- Angepasst an das bestehende Schema (wie risk_assessments / period_grades):
--   * Fach = class_subject_id (Klasse + Fach + Lehrkraft), nicht subject_id
--   * Trimester = trimester_id -> trimesters (Schuljahr + Nummer), nicht nur 1-3
--   * jede Prognose weiss, aus welchem Lauf sie stammt (run_id)
-- VOR DEM AUSFUEHREN: Backup machen.
-- ============================================================

USE edudevice_db;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    started_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at     DATETIME NULL,                              -- NULL solange der Lauf noch laeuft
    status          ENUM('running','success','failed') NOT NULL DEFAULT 'running',
    rows_processed  INT UNSIGNED NOT NULL DEFAULT 0,
    model_version   VARCHAR(50) NOT NULL,
    error_message   TEXT NULL,                                  -- nur bei status = 'failed'
    CHECK (finished_at IS NULL OR finished_at >= started_at),
    INDEX idx_runs_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS grade_forecasts (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    run_id              INT UNSIGNED NOT NULL,
    student_id          INT UNSIGNED NOT NULL,
    class_subject_id    INT UNSIGNED NOT NULL,
    trimester_id        INT UNSIGNED NOT NULL,
    predicted_grade     DECIMAL(4,2) NOT NULL,                  -- Notenskala 4-10, ungerundet
    model_version       VARCHAR(50) NOT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (predicted_grade BETWEEN 4 AND 10),
    -- pro Lauf hoechstens eine Prognose je SchuelerIn, Fach und Trimester
    UNIQUE KEY uq_forecast (run_id, student_id, class_subject_id, trimester_id),
    FOREIGN KEY (run_id)           REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id)       REFERENCES users(id)             ON DELETE CASCADE,
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id)    ON DELETE CASCADE,
    FOREIGN KEY (trimester_id)     REFERENCES trimesters(id),
    INDEX idx_forecast_student (student_id, class_subject_id, trimester_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Jorik darf in seine Ergebnis-Tabellen schreiben
GRANT INSERT, UPDATE, DELETE ON edudevice_db.pipeline_runs   TO 'jorik'@'localhost';
GRANT INSERT, UPDATE, DELETE ON edudevice_db.grade_forecasts TO 'jorik'@'localhost';
