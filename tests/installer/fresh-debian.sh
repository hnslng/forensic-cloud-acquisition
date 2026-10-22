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
    if [[ ${FCA_INSTALL_MODE:-offline} == offline ]]; then
    [[ -z $(lsblk -n -o FSTYPE /dev/disk/by-id/virtio-FCAINSTALLTEST) ]]
    mkfs.ext4 -q -m 0 /dev/disk/by-id/virtio-FCAINSTALLTEST
    mkdir -p /srv/fca/evidence /root/tls
    printf '%s\n' '/dev/disk/by-id/virtio-FCAINSTALLTEST /srv/fca/evidence ext4 defaults,nodev,nosuid,noexec 0 2' >> /etc/fstab
    mount /srv/fca/evidence
    else
      # Bootstrap must also work on a fresh VM without a preformatted data disk.
      mkdir -p /root/tls
    fi
    openssl req -x509 -newkey rsa:2048 -nodes -keyout /root/tls/ca.key -out /root/tls/ca.crt -subj /CN=FCA-disposable-test-CA -days 30 -addext 'basicConstraints=critical,CA:TRUE' -addext 'keyUsage=critical,keyCertSign,cRLSign' >/dev/null 2>&1
    openssl req -newkey rsa:2048 -nodes -keyout /root/tls/server.key -out /root/tls/server.csr -subj /CN=fca.test >/dev/null 2>&1
    printf '%s\n' 'basicConstraints=critical,CA:FALSE' 'keyUsage=critical,digitalSignature,keyEncipherment' 'extendedKeyUsage=serverAuth' 'subjectAltName=DNS:fca.test,IP:10.0.2.15' 'subjectKeyIdentifier=hash' 'authorityKeyIdentifier=keyid,issuer' > /root/tls/ext
    openssl x509 -req -in /root/tls/server.csr -CA /root/tls/ca.crt -CAkey /root/tls/ca.key -CAcreateserial -out /root/tls/server.crt -days 30 -extfile /root/tls/ext >/dev/null 2>&1
    chmod 600 /root/tls/*.key
    echo '10.0.2.15 fca.test' >> /etc/hosts
    if [[ ${FCA_INSTALL_MODE:-offline} == offline || ${FCA_INSTALL_MODE:-offline} == bootstrap ]]; then
      python3 scripts/collect_install_dependencies.py --output /root/debs
    fi
    ;;
  install)
    # No Docker/nginx preinstalled: this is the actual first installation test.
    if command -v docker >/dev/null || command -v nginx >/dev/null; then
      echo 'Test environment is not fresh: Docker or nginx already installed.' >&2
      exit 1
    fi
    # Diagnostic replay is restricted to this disposable synthetic bootstrap.
    bootstrap_diagnostics() {
      if [[ -f /var/log/fca-package-error.txt ]]; then cat /var/log/fca-package-error.txt; fi
      if command -v docker >/dev/null && [[ -f /etc/fca/secrets/initial_admin_password ]]; then
        docker compose --env-file /etc/fca/compose.env -f /etc/fca/compose.json --profile application run --rm --no-deps -v /etc/fca/secrets/initial_admin_password:/run/secrets/initial_admin_password:ro api python -m backend.manage || true
      fi
    }
    trap bootstrap_diagnostics ERR
    # Remove internet routing on this disposable guest: installation must be offline.
    ip route del default
    # Inject one failed package-manager invocation to exercise resumable bootstrap.
    mkdir /root/failing-apt
    printf '#!/bin/sh\nexit 42\n' > /root/failing-apt/apt-get
    chmod 700 /root/failing-apt/apt-get
    if [[ ${FCA_INSTALL_MODE:-offline} == bootstrap ]]; then
      python3 tests/installer/run_bootstrap.py first
    else
      if PATH="/root/failing-apt:$PATH" /root/release/install.sh --package /root/release --trusted-key /root/trusted-release.pub --config tests/installer/answers.json --yes; then exit 1; fi
    fi
    test -f /etc/fca/installation.json
    sha256sum /etc/fca/secrets/* > /root/bootstrap-secret-hashes
    if [[ ${FCA_INSTALL_MODE:-offline} == bootstrap ]]; then
      python3 tests/installer/run_bootstrap.py resume
    else
      /root/release/install.sh --package /root/release --trusted-key /root/trusted-release.pub --config tests/installer/answers.json --yes
    fi
    sha256sum -c /root/bootstrap-secret-hashes
    python3 scripts/fca_admin.py diagnose
    python3 tests/installer/seed_and_check.py seed
    sha256sum /etc/fca/secrets/* > /root/secret-hashes
    if [[ ${FCA_INSTALL_MODE:-offline} == bootstrap ]]; then
      python3 tests/installer/run_bootstrap.py repeat
      [[ -z $(lsblk -n -o FSTYPE /dev/disk/by-id/virtio-FCAINSTALLTEST) ]]
      openssl verify -x509_strict -CAfile /etc/fca/tls/ca.pem -verify_ip 10.0.2.15 /etc/fca/tls/fullchain.pem
      echo 'FRESH_DEBIAN_SIGNED_BOOTSTRAP_HTTPS_LOGIN_REPEAT_PASS'
    else
      /root/release/install.sh --package /root/release --trusted-key /root/trusted-release.pub --config tests/installer/answers.json --yes
    fi
    sha256sum -c /root/secret-hashes
    python3 tests/installer/seed_and_check.py check
    ;;
  update)
    /opt/fca-current/update.sh --package /root/release-next --trusted-key /root/trusted-release.pub --yes
    sha256sum -c /root/secret-hashes
    python3 tests/installer/seed_and_check.py check
    python3 scripts/fca_admin.py backup
    python3 tests/installer/seed_and_check.py restore-check
    printf 'ja\n' | python3 scripts/fca_admin.py rollback --version 0.6.0-test.1 --trusted-key /root/trusted-release.pub
    python3 tests/installer/seed_and_check.py check
    /opt/fca-current/update.sh --package /root/release-next --trusted-key /root/trusted-release.pub --yes
    # Missing data mount must fail even if a directory at the mountpoint remains.
    systemctl stop fca
    if mountpoint -q /srv/fca/evidence; then
      umount /srv/fca/evidence
    else
      # Same missing-storage guarantee for explicitly selected lab directories.
      mv /srv/fca/evidence /srv/fca/evidence-test-detached
      mkdir /srv/fca/evidence
    fi
    if python3 scripts/fca_admin.py guard; then exit 1; fi
    if [[ -d /srv/fca/evidence-test-detached ]]; then
      rmdir /srv/fca/evidence
      mv /srv/fca/evidence-test-detached /srv/fca/evidence
    else
      mount /srv/fca/evidence
    fi
    systemctl start fca
    python3 scripts/fca_admin.py diagnose
    ;;
  failed-update)
    if /opt/fca-current/update.sh --package /root/release-bad --trusted-key /root/trusted-release.pub --yes; then exit 1; fi
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
