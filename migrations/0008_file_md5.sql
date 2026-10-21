BEGIN;
ALTER TABLE acquisition_files ADD COLUMN md5 char(32);
INSERT INTO schema_migrations(version,name) VALUES(8,'file_md5');
COMMIT;
