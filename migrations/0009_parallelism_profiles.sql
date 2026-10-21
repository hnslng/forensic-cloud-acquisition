BEGIN;
ALTER TABLE acquisition_settings DROP CONSTRAINT acquisition_settings_file_parallelism_check;
ALTER TABLE acquisition_settings DROP CONSTRAINT acquisition_settings_account_parallelism_check;
ALTER TABLE acquisition_settings ADD CONSTRAINT acquisition_settings_file_parallelism_check CHECK(file_parallelism BETWEEN 1 AND 16);
ALTER TABLE acquisition_settings ADD CONSTRAINT acquisition_settings_account_parallelism_check CHECK(account_parallelism BETWEEN 1 AND 8);
-- Existing configuration values, jobs and file records are deliberately retained.
INSERT INTO schema_migrations(version,name) VALUES(9,'parallelism_profiles');
COMMIT;
