-- Run before 002_applications_unique.sql. All six result sets must be empty.
-- If rows are returned, ask the DB manager to reconcile them. Do not delete automatically.
USE recruitment_db;

SELECT post_id, applicant_id, COUNT(*) AS duplicate_count
FROM Applications GROUP BY post_id, applicant_id HAVING COUNT(*) > 1;

SELECT post_id, member_id, COUNT(*) AS duplicate_count
FROM ApprovedMembers GROUP BY post_id, member_id HAVING COUNT(*) > 1;

SELECT application_id, COUNT(*) AS duplicate_count
FROM ApprovedMembers GROUP BY application_id HAVING COUNT(*) > 1;

SELECT am.id AS membership_id, am.application_id
FROM ApprovedMembers am LEFT JOIN Applications a ON a.id = am.application_id
WHERE a.id IS NULL OR am.post_id <> a.post_id OR am.member_id <> a.applicant_id
   OR COALESCE(a.status, '') <> 'APPROVED';

SELECT a.id AS application_id
FROM Applications a LEFT JOIN ApprovedMembers am ON am.application_id = a.id
WHERE a.status = 'APPROVED'
GROUP BY a.id HAVING COUNT(am.id) <> 1;

SELECT p.id AS post_id, p.target_size, 1 + COUNT(am.id) AS actual_size
FROM Posts p LEFT JOIN ApprovedMembers am ON am.post_id = p.id
GROUP BY p.id, p.target_size HAVING 1 + COUNT(am.id) > p.target_size;
