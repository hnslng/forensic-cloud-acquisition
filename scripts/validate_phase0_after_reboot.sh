#!/bin/bash
set -euo pipefail
test "$(hostname)" = fca-lab
cd /opt/fca
compose() { docker compose --env-file /etc/fca/compose.env "$@"; }
test "$(cat /proc/sys/kernel/random/boot_id)" != "$(cat /var/lib/fca/validation/boot.before)"
mountpoint -q /srv/fca/evidence
(cd /srv/fca/evidence/.phase0-synthetic && sha256sum --check stream-test.sha256)
systemctl is-active qemu-guest-agent docker chrony fca-firewall
test "$(timedatectl show -p NTPSynchronized --value)" = yes
compose up -d --wait
probe='SELECT count(*), md5(string_agg(payload,'"'"','"'"' ORDER BY id)) FROM phase0_probe'
compose exec -T database psql -At -U fca_bootstrap -d fca -c "$probe" > /var/lib/fca/validation/database.after-reboot
cmp /var/lib/fca/validation/database.expected /var/lib/fca/validation/database.after-reboot
compose exec -T database psql -At -U fca_bootstrap -d fca_restore_phase0 -c "$probe" > /var/lib/fca/validation/database.restore-after-reboot
cmp /var/lib/fca/validation/database.expected /var/lib/fca/validation/database.restore-after-reboot
python3 scripts/resource_snapshot.py > /var/lib/fca/validation/resources.after-reboot.json
ss -lntup
chronyc tracking
echo PHASE0_POST_REBOOT_TESTS_PASSED
