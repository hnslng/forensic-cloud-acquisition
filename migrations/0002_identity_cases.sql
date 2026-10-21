BEGIN;
CREATE TABLE users (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 username varchar(64) UNIQUE NOT NULL CHECK (username = lower(username)),
 initials varchar(12) NOT NULL,
 password_hash text NOT NULL,
 role text NOT NULL CHECK (role IN ('admin','operator')),
 active boolean NOT NULL DEFAULT true,
 identity_provider text NOT NULL DEFAULT 'local',
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
 token_hash char(64) PRIMARY KEY,
 csrf_hash char(64) NOT NULL,
 user_id uuid NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL DEFAULT now() + interval '8 hours'
);
CREATE INDEX sessions_user ON sessions(user_id);
CREATE TABLE login_limits (
 key_hash char(64) PRIMARY KEY,
 attempts integer NOT NULL DEFAULT 0,
 window_start timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE cases (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 business_number varchar(120) UNIQUE NOT NULL,
 name varchar(160) NOT NULL DEFAULT '',
 created_at timestamptz NOT NULL DEFAULT now(),
 created_by uuid NOT NULL REFERENCES users(id),
 operator_initials varchar(12) NOT NULL,
 version integer NOT NULL DEFAULT 1,
 status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed','archived'))
);
CREATE TABLE case_members (
 case_id uuid NOT NULL REFERENCES cases(id),
 user_id uuid NOT NULL REFERENCES users(id),
 access text NOT NULL CHECK (access IN ('editor','viewer')),
 PRIMARY KEY (case_id,user_id)
);
CREATE TABLE audit_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 occurred_at timestamptz NOT NULL DEFAULT now(),
 actor_id uuid REFERENCES users(id),
 operator_initials varchar(12),
 case_id uuid REFERENCES cases(id),
 event_type varchar(64) NOT NULL,
 details jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX audit_case_time ON audit_events(case_id,id);
GRANT SELECT, INSERT, UPDATE ON users, sessions, login_limits, cases, case_members TO fca_api;
GRANT DELETE ON sessions TO fca_api;
GRANT SELECT, INSERT ON audit_events TO fca_api;
GRANT USAGE ON SEQUENCE audit_events_id_seq TO fca_api;
INSERT INTO schema_migrations (version,name) VALUES (2,'identity_and_cases');
COMMIT;
