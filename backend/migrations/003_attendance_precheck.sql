-- Read-only verification. The original DB already has these tables/columns.
-- No new table, ALTER, DROP, or seed import is required for version 0.4.0.
USE recruitment_db;

SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('Devices', 'AttendanceSessions', 'AttendanceRecords')
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- Verify a NON_UNIQUE=0 index containing session_id then member_id.
-- The original SQL and the ORM may use different index names; either is valid.
SELECT INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'AttendanceRecords'
ORDER BY INDEX_NAME, SEQ_IN_INDEX;

-- Expected no rows.
SELECT session_id, member_id, COUNT(*) AS duplicate_count
FROM AttendanceRecords GROUP BY session_id, member_id HAVING COUNT(*) > 1;

-- Expected no rows: one currently active attendance per team.
SELECT post_id, COUNT(*) AS active_count
FROM AttendanceSessions WHERE status = 'OPEN' AND expiry_time > CURRENT_TIMESTAMP
GROUP BY post_id HAVING COUNT(*) > 1;
