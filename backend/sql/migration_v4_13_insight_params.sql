-- ===========================================================================
-- Migration V4.12 -> V4.13: Zahlen zu Beobachtungen und Warnungen (Uebersetzung)
--
-- Der Auswertungslauf schreibt die Zahlen eines Satzes zusaetzlich als JSON
-- (z. B. {"average": 6.45, "gap": 0.15, "next": 7}). Die Seite baut daraus den
-- Satz in der gewaehlten Sprache; message bleibt als englischer Rueckfall.
-- Nur neue Spalten, aendert keine bestehenden Daten. VOR DEM AUSFUEHREN: Backup machen.
-- ===========================================================================

USE edudevice_db;

ALTER TABLE student_insights ADD COLUMN params JSON NULL AFTER message;
ALTER TABLE alerts           ADD COLUMN params JSON NULL AFTER message;

-- Kontrolle
SHOW COLUMNS FROM student_insights LIKE 'params';
SHOW COLUMNS FROM alerts LIKE 'params';