-- Additive UI account catalog only: no provider authentication or acquisition.
BEGIN;
CREATE TABLE cloud_accounts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 case_id uuid NOT NULL REFERENCES cases(id),
 provider text NOT NULL CHECK (provider IN ('apple','google','microsoft')),
 label varchar(160) NOT NULL CHECK (length(btrim(label)) > 0),
 created_at timestamptz NOT NULL DEFAULT now(),
 created_by uuid NOT NULL REFERENCES users(id),
 version integer NOT NULL DEFAULT 1,
 authentication_status text NOT NULL DEFAULT 'unavailable' CHECK (authentication_status = 'unavailable'),
 acquisition_status text NOT NULL DEFAULT 'unavailable' CHECK (acquisition_status = 'unavailable')
);
CREATE INDEX cloud_accounts_case_created ON cloud_accounts(case_id,created_at,id);
GRANT SELECT,INSERT,UPDATE ON cloud_accounts TO fca_api;
INSERT INTO schema_migrations(version,name) VALUES (4,'cloud_account_catalog');
COMMIT;
