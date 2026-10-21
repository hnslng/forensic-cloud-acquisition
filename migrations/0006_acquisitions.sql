BEGIN;
CREATE TABLE acquisition_settings (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 file_parallelism integer NOT NULL DEFAULT 4 CHECK(file_parallelism BETWEEN 1 AND 4),
 account_parallelism integer NOT NULL DEFAULT 2 CHECK(account_parallelism BETWEEN 1 AND 2),
 reserve_bytes bigint NOT NULL DEFAULT 2147483648 CHECK(reserve_bytes >= 1073741824)
);
INSERT INTO acquisition_settings(singleton) VALUES(true);
CREATE TABLE evidence_cases (
 case_id uuid PRIMARY KEY REFERENCES cases(id), directory text UNIQUE NOT NULL
);
CREATE TABLE evidence_accounts (
 account_id uuid NOT NULL REFERENCES cloud_accounts(id), category text NOT NULL,
 case_id uuid NOT NULL REFERENCES cases(id), directory text NOT NULL,
 PRIMARY KEY(account_id,category), UNIQUE(case_id,directory)
);
CREATE TABLE acquisitions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 case_id uuid NOT NULL REFERENCES cases(id), account_id uuid NOT NULL REFERENCES cloud_accounts(id),
 category text NOT NULL, scope_path text NOT NULL DEFAULT '',
 requested_by uuid NOT NULL REFERENCES users(id), operator_initials text NOT NULL,
 status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','pausing','paused','failed','completed','incomplete')),
 directory text UNIQUE NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 started_at timestamptz, ended_at timestamptz, inventory_complete boolean NOT NULL DEFAULT false, total_known boolean NOT NULL DEFAULT false,
 bytes_done bigint NOT NULL DEFAULT 0, bytes_total bigint NOT NULL DEFAULT 0,
 files_done bigint NOT NULL DEFAULT 0, speed bigint NOT NULL DEFAULT 0,
 reason text, account_identity jsonb NOT NULL DEFAULT '{}', resource_observations jsonb NOT NULL DEFAULT '{}', limitations jsonb NOT NULL DEFAULT '[]',
 heartbeat timestamptz
);
CREATE UNIQUE INDEX one_active_account_run ON acquisitions(account_id) WHERE status IN ('queued','running','pausing','paused');
CREATE TABLE acquisition_files (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 acquisition_id uuid NOT NULL REFERENCES acquisitions(id), source_id text NOT NULL,
 relative_path text NOT NULL, metadata jsonb NOT NULL,
 size bigint NOT NULL, status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','completed','failed')),
 bytes_done bigint NOT NULL DEFAULT 0, attempts integer NOT NULL DEFAULT 0,
 sha256 char(64), reason text,
 UNIQUE(acquisition_id,source_id), UNIQUE(acquisition_id,relative_path)
);
CREATE INDEX acquisition_files_queue ON acquisition_files(acquisition_id,status,id);
GRANT SELECT,INSERT,UPDATE ON evidence_cases,evidence_accounts,acquisitions,acquisition_files TO fca_api;
GRANT SELECT,UPDATE ON acquisition_settings TO fca_api;
GRANT USAGE ON SEQUENCE acquisition_files_id_seq TO fca_api;
INSERT INTO schema_migrations(version,name) VALUES(6,'durable_acquisitions');
COMMIT;
