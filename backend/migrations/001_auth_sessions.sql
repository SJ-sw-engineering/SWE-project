-- Select recruitment_db in the SQL editor before running this file.
-- Additive migration: does not drop tables or replace existing users/posts.
CREATE TABLE IF NOT EXISTS AuthSessions (
    id VARCHAR(32) PRIMARY KEY,
    username VARCHAR(20) NOT NULL,
    refresh_token_hash VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    revoked_at DATETIME(6) NULL,
    INDEX ix_AuthSessions_username (username),
    FOREIGN KEY (username) REFERENCES Users(username) ON DELETE CASCADE
);
