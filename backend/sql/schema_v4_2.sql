-- ============================================================
-- EduDevice database schema (MySQL 8.0.16+) - Version 4.2
-- Based on Version 3 (Gridi Bushati), extended for the
-- data-science pipeline (trimesters, classes, M1/M2/M3 grading,
-- lessons, excuses, risk assessments, alerts).
--
-- Changes 4 -> 4.1:
--   1. quizzes: subject_id -> class_subject_id (a live quiz belongs to a class)
--   2. quiz_results: UNIQUE (quiz_id, student_id) (one submission per student)
--   3. grades, period_grades: FK to class_subjects without ON DELETE CASCADE
--      (deleting a teaching assignment must not silently delete grades)
--   4. attendance: redundant index idx_attendance_student removed
--      (already covered by UNIQUE KEY uq_attendance)
--
-- Changes 4.1 -> 4.2:
--   5. users: name -> first_name + last_name, username (UNIQUE) added
--
-- Naming rule: existing tables/columns/ENUM values from V3 are kept
-- unchanged (incl. German ENUM values); new tables/columns use English.
--
-- WARNING: DROP DATABASE deletes all existing data.
-- ============================================================

DROP DATABASE IF EXISTS edudevice_db;
CREATE DATABASE edudevice_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE edudevice_db;


-- ============================================================
-- Users
-- ============================================================

-- 4.2: name split into first_name / last_name, username added
--      (Ziel-M-4: login with username/password)
CREATE TABLE users (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,   -- FIX: UNSIGNED (was INT, broke all FKs)
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    username        VARCHAR(50) NOT NULL UNIQUE,
    role            ENUM('schueler','lehrkraft','admin') NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- ============================================================
-- School structure (NEW)
-- ============================================================

CREATE TABLE school_years (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    label           VARCHAR(20) NOT NULL UNIQUE,               -- e.g. '2026/27'
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    CHECK (end_date > start_date)
) ENGINE=InnoDB;

CREATE TABLE trimesters (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    school_year_id  INT UNSIGNED NOT NULL,
    number          TINYINT UNSIGNED NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    UNIQUE KEY uq_trimester (school_year_id, number),
    CHECK (number BETWEEN 1 AND 3),
    CHECK (end_date > start_date),
    FOREIGN KEY (school_year_id) REFERENCES school_years(id)
) ENGINE=InnoDB;

CREATE TABLE classes (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    school_year_id  INT UNSIGNED NOT NULL,
    name            VARCHAR(20) NOT NULL,                      -- e.g. '4A'
    UNIQUE KEY uq_class (school_year_id, name),
    FOREIGN KEY (school_year_id) REFERENCES school_years(id)
) ENGINE=InnoDB;

CREATE TABLE student_classes (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id      INT UNSIGNED NOT NULL,
    class_id        INT UNSIGNED NOT NULL,
    UNIQUE KEY uq_student_class (student_id, class_id),
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (class_id)   REFERENCES classes(id)
) ENGINE=InnoDB;

-- CHANGED: teacher_id removed; the teacher now depends on the class
-- and is stored in class_subjects.
CREATE TABLE subjects (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- NEW: which teacher teaches which subject to which class (Lehrfaecherverteilung)
CREATE TABLE class_subjects (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    class_id        INT UNSIGNED NOT NULL,
    subject_id      INT UNSIGNED NOT NULL,
    teacher_id      INT UNSIGNED NOT NULL,
    UNIQUE KEY uq_class_subject (class_id, subject_id),
    FOREIGN KEY (class_id)   REFERENCES classes(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (teacher_id) REFERENCES users(id)             -- no cascade: deleting a teacher must not delete grades
) ENGINE=InnoDB;


-- ============================================================
-- Timetable, lessons, excuses, attendance
-- ============================================================

-- CHANGED: subject_id -> class_subject_id
CREATE TABLE timetable (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    class_subject_id    INT UNSIGNED NOT NULL,
    weekday             ENUM('Mo','Di','Mi','Do','Fr') NOT NULL,
    start_time          TIME NOT NULL,
    end_time            TIME NOT NULL,
    room                VARCHAR(50),
    CHECK (end_time > start_time),
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- NEW: one row per lesson that actually takes place (denominator for the 20%/30% rule)
CREATE TABLE lessons (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    timetable_id    INT UNSIGNED NOT NULL,
    date            DATE NOT NULL,
    cancelled       BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE KEY uq_lesson (timetable_id, date),
    FOREIGN KEY (timetable_id) REFERENCES timetable(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- NEW
CREATE TABLE excuses (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id      INT UNSIGNED NOT NULL,
    date_from       DATE NOT NULL,
    date_to         DATE NOT NULL,
    reason          TEXT,
    status          ENUM('pending','accepted','rejected') NOT NULL DEFAULT 'pending',
    submitted_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (date_to >= date_from),
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- CHANGED: lesson_id now has a real FK, excuse_id added, one record per student and lesson
-- 4.1: separate index on student_id removed, uq_attendance already starts with student_id
CREATE TABLE attendance (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id      INT UNSIGNED NOT NULL,
    lesson_id       INT UNSIGNED NOT NULL,
    status          ENUM('anwesend','abwesend','verspaetet') NOT NULL,
    excuse_id       INT UNSIGNED NULL,
    UNIQUE KEY uq_attendance (student_id, lesson_id),
    FOREIGN KEY (student_id) REFERENCES users(id)   ON DELETE CASCADE,
    FOREIGN KEY (lesson_id)  REFERENCES lessons(id) ON DELETE CASCADE,
    FOREIGN KEY (excuse_id)  REFERENCES excuses(id) ON DELETE SET NULL
) ENGINE=InnoDB;


-- ============================================================
-- Homework
-- ============================================================

-- CHANGED: subject_id -> class_subject_id, created_at added
CREATE TABLE homework (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    class_subject_id    INT UNSIGNED NOT NULL,
    description         TEXT NOT NULL,
    due_date            DATETIME NOT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id) ON DELETE CASCADE,
    INDEX idx_homework_due_date (due_date)
) ENGINE=InnoDB;

-- CHANGED: status added (to mark excused homework)
-- late    = confirmed_at > homework.due_date   (computed)
-- missing = no row after due_date              (computed)
CREATE TABLE homework_confirmations (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    homework_id     INT UNSIGNED NOT NULL,
    student_id      INT UNSIGNED NOT NULL,
    confirmed_at    TIMESTAMP NULL DEFAULT NULL,
    status          ENUM('confirmed','excused') NOT NULL DEFAULT 'confirmed',
    UNIQUE KEY uq_homework_confirmation (homework_id, student_id),
    FOREIGN KEY (homework_id) REFERENCES homework(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id)  REFERENCES users(id)    ON DELETE CASCADE
) ENGINE=InnoDB;


-- ============================================================
-- Grades
-- ============================================================

-- CHANGED: subject_id -> class_subject_id; category, weight, homework_id,
-- created_at added; value restricted to 4-10.
-- Component mapping (in the pipeline): schularbeit -> M2, project -> M3, rest -> M1.
-- Trimester is derived from `date` via the trimesters table.
-- 4.1: FK to class_subjects without cascade, so grades cannot be deleted by accident.
CREATE TABLE grades (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id          INT UNSIGNED NOT NULL,
    class_subject_id    INT UNSIGNED NOT NULL,
    category            ENUM('homework','mini_test','oral','presentation',
                             'classwork','participation','behaviour',
                             'schularbeit','project') NOT NULL,
    weight              DECIMAL(4,2) NOT NULL DEFAULT 1.00,
    value               DECIMAL(3,1) NOT NULL,
    date                DATE NOT NULL DEFAULT (CURRENT_DATE),   -- when the performance happened
    homework_id         INT UNSIGNED NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- when it was entered
    CHECK (value BETWEEN 4 AND 10),
    CHECK (weight > 0),
    FOREIGN KEY (student_id)       REFERENCES users(id)          ON DELETE CASCADE,
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id),
    FOREIGN KEY (homework_id)      REFERENCES homework(id)       ON DELETE SET NULL,
    INDEX idx_grades_student_subject_date (student_id, class_subject_id, date),
    INDEX idx_grades_date (date)
) ENGINE=InnoDB;

-- NEW: official component grades per trimester + final grade (training label)
-- 4.1: FK to class_subjects without cascade (official grades are protected).
CREATE TABLE period_grades (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id          INT UNSIGNED NOT NULL,
    class_subject_id    INT UNSIGNED NOT NULL,
    trimester_id        INT UNSIGNED NULL,                     -- NULL for M3 and FINAL
    kind                ENUM('M1','M2','M3','FINAL') NOT NULL,
    value               DECIMAL(4,2) NOT NULL,                 -- exact, unrounded
    finalized_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- MySQL allows several NULLs in a UNIQUE key; mapping NULL to 0
    -- prevents e.g. two FINAL rows for the same student and subject.
    trimester_key       INT UNSIGNED AS (COALESCE(trimester_id, 0)) STORED,
    UNIQUE KEY uq_period_grade (student_id, class_subject_id, kind, trimester_key),
    CHECK (value BETWEEN 4 AND 10),
    CHECK (
        (kind IN ('M1','M2')    AND trimester_id IS NOT NULL) OR
        (kind IN ('M3','FINAL') AND trimester_id IS NULL)
    ),
    FOREIGN KEY (student_id)       REFERENCES users(id)          ON DELETE CASCADE,
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id),
    FOREIGN KEY (trimester_id)     REFERENCES trimesters(id)     -- no cascade: MySQL forbids it with the CHECK/generated column
) ENGINE=InnoDB;


-- ============================================================
-- Quizzes
-- ============================================================

-- 4.1: subject_id -> class_subject_id (a live quiz is sent to one class)
CREATE TABLE quizzes (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title               VARCHAR(150) NOT NULL,
    class_subject_id    INT UNSIGNED NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id)   -- no cascade: protects quiz results
) ENGINE=InnoDB;

-- 4.1: UNIQUE (quiz_id, student_id), one submission per student and quiz
CREATE TABLE quiz_results (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    quiz_id         INT UNSIGNED NOT NULL,
    student_id      INT UNSIGNED NOT NULL,
    score           INT NOT NULL,
    submitted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_quiz_result (quiz_id, student_id),
    FOREIGN KEY (quiz_id)    REFERENCES quizzes(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id)   ON DELETE CASCADE,
    INDEX idx_quiz_results_student (student_id)
) ENGINE=InnoDB;


-- ============================================================
-- Data-science pipeline output (NEW)
-- ============================================================

CREATE TABLE risk_assessments (
    id                      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id              INT UNSIGNED NOT NULL,
    class_subject_id        INT UNSIGNED NOT NULL,
    computed_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_version           VARCHAR(50) NOT NULL,
    status                  ENUM('secured_pass','undecided','fail_unavoidable') NOT NULL,
    fail_probability        DECIMAL(5,4) NULL,                 -- NULL when decided by rule
    predicted_final         DECIMAL(4,2) NOT NULL,
    predicted_low           DECIMAL(4,2) NOT NULL,
    predicted_high          DECIMAL(4,2) NOT NULL,
    required_remaining_avg  DECIMAL(4,2) NULL,
    absence_rate            DECIMAL(5,4) NOT NULL,
    CHECK (fail_probability IS NULL OR fail_probability BETWEEN 0 AND 1),
    CHECK (absence_rate BETWEEN 0 AND 1),
    CHECK (predicted_low <= predicted_final AND predicted_final <= predicted_high),
    FOREIGN KEY (student_id)       REFERENCES users(id)          ON DELETE CASCADE,
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id) ON DELETE CASCADE,
    INDEX idx_risk_student_subject_time (student_id, class_subject_id, computed_at)
) ENGINE=InnoDB;

CREATE TABLE alerts (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id          INT UNSIGNED NOT NULL,
    class_subject_id    INT UNSIGNED NOT NULL,
    type                ENUM('fail_risk','deterioration','attendance_20',
                             'attendance_30','attendance_trend','homework') NOT NULL,
    severity            ENUM('info','warning','critical') NOT NULL,
    message             TEXT NOT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at     DATETIME NULL,
    FOREIGN KEY (student_id)       REFERENCES users(id)          ON DELETE CASCADE,
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id) ON DELETE CASCADE
) ENGINE=InnoDB;


-- ============================================================
-- Communication
-- ============================================================

-- CHANGED: alert_id added (links an early-warning email to its alert)
CREATE TABLE email_log (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    recipient_email VARCHAR(255) NOT NULL,
    email_type      ENUM('fruehwarnung','hausaufgaben_erinnerung') NOT NULL,
    alert_id        INT UNSIGNED NULL,
    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE notifications (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         INT UNSIGNED NOT NULL,
    type            VARCHAR(50) NOT NULL,
    message         TEXT NOT NULL,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notifications_user (user_id)
) ENGINE=InnoDB;

CREATE TABLE messages (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    sender_id       INT UNSIGNED NOT NULL,
    receiver_id     INT UNSIGNED NULL,
    room_id         VARCHAR(100) NULL,
    content         TEXT NOT NULL,
    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id)   REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_messages_room (room_id)
) ENGINE=InnoDB;

CREATE TABLE sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_sessions_expires_at (expires_at)
) ENGINE=InnoDB;
