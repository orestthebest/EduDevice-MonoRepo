-- ============================================================
-- EduDevice Schema V4.5 (Migration von V4.4)
-- Benutzerprofil: Profilbild (Wunsch von Orest, 28.10.2026)
--   users.profile_image = Dateiname im Ordner /srv/edudevice/uploads/avatars
--   (z. B. "8-1761680000000.webp"), NULL = kein Bild
-- VOR DEM AUSFUEHREN: Backup machen.
-- ============================================================

USE edudevice_db;

ALTER TABLE users
    ADD COLUMN profile_image VARCHAR(255) NULL AFTER email;
