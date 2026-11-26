-- ===========================================================================
-- Migration V4.11 -> V4.12: Passwort zuruecksetzen per E-Mail (Ziel-M-1, API 2.13)
--
-- Neue Tabelle password_resets. Gespeichert wird nur der SHA-256-Hash des Tokens,
-- der Token selbst steht nur im Link in der Mail. Ein Link gilt 30 Minuten und nur einmal.
-- Aendert keine bestehenden Daten. VOR DEM AUSFUEHREN: Backup machen.
-- ===========================================================================

USE edudevice_db;

CREATE TABLE IF NOT EXISTS password_resets (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     INT UNSIGNED NOT NULL,
    token_hash  CHAR(64)     NOT NULL,
    created_at  DATETIME     NOT NULL,
    expires_at  DATETIME     NOT NULL,
    used_at     DATETIME     NULL,
    UNIQUE KEY uq_password_resets_token (token_hash),
    KEY idx_password_resets_user (user_id, created_at),
    CONSTRAINT fk_password_resets_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Kontrolle
SHOW CREATE TABLE password_resets;
