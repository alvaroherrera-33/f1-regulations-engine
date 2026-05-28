-- Migration 004: query_logs retention
-- Adds an index on created_at for efficient range queries and a prune function
-- that deletes logs older than 90 days. Idempotent (safe to re-run).

-- Index for fast date-based pruning and stats queries
CREATE INDEX IF NOT EXISTS idx_query_logs_created_at
    ON query_logs (created_at);

-- Prune function: deletes records older than retention_days (default 90)
-- Usage: SELECT prune_old_query_logs();          -- default 90 days
--        SELECT prune_old_query_logs(30);         -- custom 30 days
CREATE OR REPLACE FUNCTION prune_old_query_logs(retention_days INT DEFAULT 90)
RETURNS TABLE(deleted_count BIGINT) AS $$
DECLARE
    cutoff TIMESTAMPTZ;
    cnt    BIGINT;
BEGIN
    cutoff := NOW() - (retention_days || ' days')::INTERVAL;
    DELETE FROM query_logs WHERE created_at < cutoff;
    GET DIAGNOSTICS cnt = ROW_COUNT;
    RETURN QUERY SELECT cnt;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Revoke execute from public; only postgres / service_role can prune
REVOKE EXECUTE ON FUNCTION prune_old_query_logs(INT) FROM PUBLIC;
