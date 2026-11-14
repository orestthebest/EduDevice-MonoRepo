-- ===========================================================================
-- sim_trimesters.sql - master data, NOT demo data.
--
-- The trimesters table is empty. period_grades requires a trimester_id for
-- every M1 and M2 row, so nothing can be computed until these exist.
--
-- THE DATES BELOW ARE A PROPOSAL, derived from the school year window
-- (2026-09-07 .. 2027-07-02) by splitting it in three. They are NOT the
-- school's real trimester boundaries. Confirm them before running this.
-- ===========================================================================

INSERT INTO trimesters (school_year_id, number, start_date, end_date) VALUES (1, 1, '2026-09-07', '2026-12-04');
INSERT INTO trimesters (school_year_id, number, start_date, end_date) VALUES (1, 2, '2026-12-07', '2027-03-19');
INSERT INTO trimesters (school_year_id, number, start_date, end_date) VALUES (1, 3, '2027-03-22', '2027-07-02');

SELECT * FROM trimesters ORDER BY number;
