USE recruitment_db;

-- Expected three unique indexes (NON_UNIQUE = 0), including both columns of composite indexes.
SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE() AND INDEX_NAME IN (
    'uq_applications_post_applicant', 'uq_approved_post_member', 'uq_approved_application'
)
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;

-- Expected no rows: cached count differs from approved memberships.
SELECT p.id, p.current_size, 1 + COUNT(am.id) AS actual_size
FROM Posts p LEFT JOIN ApprovedMembers am ON am.post_id = p.id
GROUP BY p.id, p.current_size HAVING p.current_size IS NULL OR p.current_size <> 1 + COUNT(am.id);

-- Expected no rows: full teams must be closed.
SELECT id, target_size, current_size, status FROM Posts
WHERE current_size >= target_size AND (status IS NULL OR status <> 'CLOSED');

-- Expected no rows: every approved application has exactly one matching member.
SELECT a.id AS application_id
FROM Applications a LEFT JOIN ApprovedMembers am ON am.application_id = a.id
WHERE a.status = 'APPROVED'
GROUP BY a.id, a.post_id, a.applicant_id
HAVING COUNT(am.id) <> 1
    OR SUM(CASE WHEN am.post_id = a.post_id AND am.member_id = a.applicant_id THEN 1 ELSE 0 END) <> 1;
