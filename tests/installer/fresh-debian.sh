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
    ./install.sh --package /root/release --trusted-key /root/trusted-release.pub --config tests/installer/answers.json --yes
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
    # Missing data mount must fail even if a directory at the mountpoint remains.
    systemctl stop fca
    umount /srv/fca/evidence
    if python3 scripts/fca_admin.py guard; then exit 1; fi
    mount /srv/fca/evidence
    systemctl start fca
    python3 scripts/fca_admin.py diagnose
    ;;
  reboot-check)
    python3 scripts/fca_admin.py diagnose
    python3 tests/installer/seed_and_check.py check
    sha256sum -c /root/secret-hashes
    echo 'FRESH_DEBIAN_INSTALL_UPDATE_BACKUP_REBOOT_PASS'
    ;;
  *) exit 2 ;;
esac
