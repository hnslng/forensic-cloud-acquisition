-- Additive authentication throttling only; previous cloud/catalog rows stay intact.
BEGIN;
CREATE TABLE cloud_auth_limits (
 account_id uuid PRIMARY KEY REFERENCES cloud_accounts(id),
 attempts integer NOT NULL DEFAULT 0,
 window_start timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT,INSERT,UPDATE ON cloud_auth_limits TO fca_api;
INSERT INTO schema_migrations(version,name) VALUES (5,'cloud_auth_attempt_limits');
COMMIT;
