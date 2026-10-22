#!/usr/bin/env bash
# ONLY inside the disposable QEMU guest launched by scripts/test_fresh_debian.sh.
set -euo pipefail
[[ $(cat /sys/class/dmi/id/product_name) == *QEMU* || $(cat /sys/class/dmi/id/sys_vendor) == *QEMU* ]]
[[ -f /root/FCA_INSTALLER_DISPOSABLE_GUEST ]]
[[ -b /dev/disk/by-id/virtio-FCAINSTALLTEST ]]
cd /root/source
case "${1:-}" in
  prepare)
    # This is the newly created, uniquely identified test disk, never a lab disk.
    [[ -z $(lsblk -n -o FSTYPE /dev/disk/by-id/virtio-FCAINSTALLTEST) ]]
    mkfs.ext4 -q -m 0 /dev/disk/by-id/virtio-FCAINSTALLTEST
    mkdir -p /srv/fca/evidence /root/tls
    printf '%s\n' '/dev/disk/by-id/virtio-FCAINSTALLTEST /srv/fca/evidence ext4 defaults,nodev,nosuid,noexec 0 2' >> /etc/fstab
    mount /srv/fca/evidence
    openssl req -x509 -newkey rsa:2048 -nodes -keyout /root/tls/ca.key -out /root/tls/ca.crt -subj /CN=FCA-disposable-test-CA -days 2 >/dev/null 2>&1
    openssl req -newkey rsa:2048 -nodes -keyout /root/tls/server.key -out /root/tls/server.csr -subj /CN=fca.test >/dev/null 2>&1
    printf '%s\n' 'subjectAltName=DNS:fca.test,IP:10.0.2.15' > /root/tls/ext
    openssl x509 -req -in /root/tls/server.csr -CA /root/tls/ca.crt -CAkey /root/tls/ca.key -CAcreateserial -out /root/tls/server.crt -days 30 -extfile /root/tls/ext >/dev/null 2>&1
    chmod 600 /root/tls/*.key
    echo '10.0.2.15 fca.test' >> /etc/hosts
    python3 scripts/collect_install_dependencies.py --output /root/debs
    ;;
  install)
    # No Docker/nginx preinstalled: this is the actual first installation test.
    ! command -v docker
    # Diagnostic replay is restricted to this disposable synthetic bootstrap.
    bootstrap_diagnostics() {
      if [[ -f /var/log/fca-package-error.txt ]]; then cat /var/log/fca-package-error.txt; fi
      if command -v docker >/dev/null && [[ -f /etc/fca/secrets/initial_admin_password ]]; then
        docker compose --env-file /etc/fca/compose.env -f /etc/fca/compose.json --profile application run --rm --no-deps --pull never -v /etc/fca/secrets/initial_admin_password:/run/secrets/initial_admin_password:ro api python -m backend.manage || true
      fi
    }
    trap bootstrap_diagnostics ERR
    # Remove internet routing on this disposable guest: installation must be offline.
    ip route del default
    # Inject one failed package-manager invocation to exercise resumable bootstrap.
    mkdir /root/failing-apt
    printf '#!/bin/sh\nexit 42\n' > /root/failing-apt/apt-get
    chmod 700 /root/failing-apt/apt-get
    if PATH="/root/failing-apt:$PATH" ./install.sh --package /root/release --trusted-key /root/trusted-release.pub --config tests/installer/answers.json --yes; then exit 1; fi
    test -f /etc/fca/installation.json
    sha256sum /etc/fca/secrets/* > /root/bootstrap-secret-hashes
    ./install.sh --package /root/release --trusted-key /root/trusted-release.pub --config tests/installer/answers.json --yes
    sha256sum -c /root/bootstrap-secret-hashes
    python3 scripts/fca_admin.py diagnose
    python3 tests/installer/seed_and_check.py seed
    sha256sum /etc/fca/secrets/* > /root/secret-hashes
    ./install.sh --package /root/release --trusted-key /root/trusted-release.pub --config tests/installer/answers.json --yes
    sha256sum -c /root/secret-hashes
    python3 tests/installer/seed_and_check.py check
    ;;
  update)
    ./update.sh --package /root/release-next --trusted-key /root/trusted-release.pub --yes
    sha256sum -c /root/secret-hashes
    python3 tests/installer/seed_and_check.py check
    python3 scripts/fca_admin.py backup
    python3 tests/installer/seed_and_check.py restore-check
    printf 'ja\n' | python3 scripts/fca_admin.py rollback --version 0.6.0-test.1 --trusted-key /root/trusted-release.pub
    python3 tests/installer/seed_and_check.py check
    ./update.sh --package /root/release-next --trusted-key /root/trusted-release.pub --yes
    # Missing data mount must fail even if a directory at the mountpoint remains.
    systemctl stop fca
    umount /srv/fca/evidence
    if python3 scripts/fca_admin.py guard; then exit 1; fi
    mount /srv/fca/evidence
    systemctl start fca
    python3 scripts/fca_admin.py diagnose
    ;;
  failed-update)
    if ./update.sh --package /root/release-bad --trusted-key /root/trusted-release.pub --yes; then exit 1; fi
    test "$(basename "$(readlink -f /opt/fca-current)")" = 0.6.0-test.2
    python3 scripts/fca_admin.py diagnose
    python3 tests/installer/seed_and_check.py check
    sha256sum -c /root/secret-hashes
    ;;
  reboot-check)
    python3 scripts/fca_admin.py diagnose
    python3 tests/installer/seed_and_check.py check
    sha256sum -c /root/secret-hashes
    echo 'FRESH_DEBIAN_INSTALL_UPDATE_BACKUP_REBOOT_PASS'
    ;;
  *) exit 2 ;;
esac
