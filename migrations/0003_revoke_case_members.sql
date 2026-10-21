BEGIN;
GRANT DELETE ON case_members TO fca_api;
INSERT INTO schema_migrations (version,name) VALUES (3,'revoke_case_members');
COMMIT;
