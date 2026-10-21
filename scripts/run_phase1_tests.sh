#!/bin/bash
# Run as root on the guest or an ephemeral CI runner with Docker installed.
set -euo pipefail
cd "${FCA_PROJECT_ROOT:-/opt/fca}"
compose() { docker compose --env-file /etc/fca/compose.env "$@"; }
testcompose() { docker compose --env-file /etc/fca/compose.env -f compose.yaml -f compose.test.yaml --profile application "$@"; }
cleanup() { compose exec -T database dropdb --if-exists --force -U fca_bootstrap fca_test_phase1; }
trap cleanup EXIT
cleanup
compose exec -T database createdb -U fca_bootstrap fca_test_phase1
compose exec -T database psql -v ON_ERROR_STOP=1 -U fca_bootstrap -d fca_test_phase1 < migrations/0001_bootstrap.sql
compose exec -T database psql -v ON_ERROR_STOP=1 -U fca_bootstrap -d fca_test_phase1 <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO fca_api,fca_migrate;
GRANT CREATE ON SCHEMA public TO fca_migrate;
ALTER TABLE schema_migrations OWNER TO fca_migrate;
SQL
{ printf 'SET ROLE fca_migrate;\n'; cat migrations/0002_identity_cases.sql; } | compose exec -T database psql -v ON_ERROR_STOP=1 -U fca_bootstrap -d fca_test_phase1
{ printf 'SET ROLE fca_migrate;\n'; cat migrations/0003_revoke_case_members.sql; } | compose exec -T database psql -v ON_ERROR_STOP=1 -U fca_bootstrap -d fca_test_phase1
testcompose build api
testcompose run --rm --no-deps api
