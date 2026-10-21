#!/bin/bash
# Guest-only synthetic acceptance. Run once on the new lab VM, before reboot.
set -euo pipefail
test "$(hostname)" = fca-lab
exec 9>/run/fca-phase0-validation.lock
flock -n 9
cd /opt/fca
compose() { docker compose --env-file /etc/fca/compose.env "$@"; }
install -d -m 0700 /var/lib/fca/validation /var/backups/fca
mountpoint -q /srv/fca/evidence
findmnt -n -o OPTIONS /srv/fca/evidence | grep -q noexec
getent hosts cloud.debian.org
curl --fail --silent --show-error --connect-timeout 10 --max-time 30 --output /dev/null https://deb.debian.org/debian/dists/trixie/Release
test "$(timedatectl show -p NTPSynchronized --value)" = yes
systemctl is-active qemu-guest-agent docker chrony fca-firewall
docker run --rm hello-world
compose config --quiet
compose up -d --wait
compose exec -T database psql -v ON_ERROR_STOP=1 -U fca_bootstrap -d fca < migrations/0001_bootstrap.sql
compose exec -T database psql -v ON_ERROR_STOP=1 -U fca_bootstrap -d fca <<'SQL'
CREATE TABLE phase0_probe (id integer PRIMARY KEY, payload text NOT NULL);
INSERT INTO phase0_probe SELECT n, md5('FCA-SYNTHETIC-' || n::text) FROM generate_series(1,1000) n;
SQL
probe='SELECT count(*), md5(string_agg(payload,'"'"','"'"' ORDER BY id)) FROM phase0_probe'
compose exec -T database psql -At -U fca_bootstrap -d fca -c "$probe" > /var/lib/fca/validation/database.expected
compose exec -T database pg_dump -U fca_bootstrap -Fc fca > /var/backups/fca/phase0.dump
compose exec -T database createdb -U fca_bootstrap fca_restore_phase0
compose exec -T database pg_restore -U fca_bootstrap --exit-on-error -d fca_restore_phase0 < /var/backups/fca/phase0.dump
compose exec -T database psql -At -U fca_bootstrap -d fca_restore_phase0 -c "$probe" > /var/lib/fca/validation/database.restored
cmp /var/lib/fca/validation/database.expected /var/lib/fca/validation/database.restored
sha256sum /var/backups/fca/phase0.dump
python3 - <<'PY'
from pathlib import Path
import hashlib, json, os, time
root=Path('/srv/fca/evidence/.phase0-synthetic')
root.mkdir(mode=0o700)
digest=hashlib.sha256()
start=time.monotonic()
with (root/'stream-test.bin').open('xb') as f:
    for _ in range(256):
        chunk=os.urandom(1024*1024)
        digest.update(chunk)
        f.write(chunk)
    f.flush(); os.fsync(f.fileno())
expected=digest.hexdigest()
with (root/'stream-test.bin').open('rb') as f:
    actual=hashlib.file_digest(f,'sha256').hexdigest()
assert actual==expected
(root/'stream-test.sha256').write_text(expected+'  stream-test.bin\n')
print(json.dumps(dict(synthetic_bytes=256*1024**2,sha256=expected,seconds=round(time.monotonic()-start,2))))
PY
cat /proc/sys/kernel/random/boot_id > /var/lib/fca/validation/boot.before
python3 scripts/resource_snapshot.py > /var/lib/fca/validation/resources.before-reboot.json
compose ps
echo PHASE0_PRE_REBOOT_TESTS_PASSED
