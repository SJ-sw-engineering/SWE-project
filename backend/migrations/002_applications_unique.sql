-- Run once, only after all precheck result sets are empty.
-- Pause API writes while applying. MySQL/TiDB DDL is not an all-or-nothing transaction.
-- If partially applied, inspect SHOW INDEX and run only the missing ALTER statement.
USE recruitment_db;

ALTER TABLE Applications
    ADD CONSTRAINT uq_applications_post_applicant UNIQUE (post_id, applicant_id);

ALTER TABLE ApprovedMembers
    ADD CONSTRAINT uq_approved_post_member UNIQUE (post_id, member_id),
    ADD CONSTRAINT uq_approved_application UNIQUE (application_id);

START TRANSACTION;
UPDATE Posts p SET current_size = 1 + (
    SELECT COUNT(*) FROM ApprovedMembers am WHERE am.post_id = p.id
);
UPDATE Posts SET status = 'CLOSED' WHERE current_size >= target_size;
COMMIT;
