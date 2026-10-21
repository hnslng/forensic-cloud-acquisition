-- Phase 0 smoke test: transactional baseline, no case or identity schema yet.
BEGIN;
CREATE TABLE schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO schema_migrations (version, name) VALUES (1, 'infrastructure_bootstrap');
COMMIT;
