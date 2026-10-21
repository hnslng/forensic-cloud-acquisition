#!/bin/bash
# Only inside the newly approved FCA VM. No host/other-guest changes.
set -euo pipefail
test "$(hostname)" = fca-lab
test "$(id -u)" -eq 0
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git openssl chrony iptables dnsutils
timedatectl set-timezone Europe/Vienna
systemctl enable --now chrony qemu-guest-agent
install -d -m 0755 /etc/apt/keyrings
curl --fail --silent --show-error https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<'EOF'
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: trixie
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
install -d -m 0750 /etc/fca /var/lib/fca /var/backups/fca /opt/fca
install -d -m 0700 /etc/fca/secrets
if [ ! -f /etc/fca/secrets/postgres_password ]; then
  (umask 077; openssl rand -hex 32 > /etc/fca/secrets/postgres_password)
fi
cat > /etc/fca/compose.env <<'EOF'
FCA_STATE_ROOT=/var/lib/fca
FCA_POSTGRES_PASSWORD_FILE=/etc/fca/secrets/postgres_password
EOF
chmod 0640 /etc/fca/compose.env
install -d /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/fca.conf <<'EOF'
[Journal]
Storage=persistent
SystemMaxUse=128M
RuntimeMaxUse=32M
MaxRetentionSec=1month
EOF
systemctl restart systemd-journald
# Format ONLY the approved unformatted 32-GiB evidence disk by exact serial.
python3 - <<'PY'
import json,subprocess,pathlib
disks=json.loads(subprocess.check_output(['lsblk','--json','--bytes','-o','PATH,SERIAL,TYPE,FSTYPE,SIZE,MOUNTPOINTS']))['blockdevices']
disk=next(d for d in disks if d.get('serial')=='FCA105EVIDENCE')
assert disk['type']=='disk' and disk['size']==32*1024**3
assert not disk.get('children'), 'Evidence disk unexpectedly partitioned'
assert not any(disk.get('mountpoints') or []), 'Evidence disk already mounted; inspect before rerun'
assert not disk['fstype'], 'Refusing to reformat existing filesystem'
subprocess.run(['mkfs.ext4','-m','1','-L','FCA_TESTDATA',disk['path']],check=True)
uuid=subprocess.check_output(['blkid','-s','UUID','-o','value',disk['path']],text=True).strip()
pathlib.Path('/srv/fca/evidence').mkdir(parents=True,exist_ok=True)
fstab=pathlib.Path('/etc/fstab')
pathlib.Path('/etc/fstab.before-fca').write_bytes(fstab.read_bytes())
with fstab.open('a') as f: f.write(f'\nUUID={uuid} /srv/fca/evidence ext4 defaults,nodev,nosuid,noexec 0 2\n')
subprocess.run(['mount','/srv/fca/evidence'],check=True)
pathlib.Path('/srv/fca/evidence').chmod(0o750)
PY
cat > /usr/local/sbin/fca-firewall <<'EOF'
#!/bin/sh
set -eu
iptables -N FCA-INPUT 2>/dev/null || true
iptables -F FCA-INPUT
iptables -A FCA-INPUT -i lo -j ACCEPT
iptables -A FCA-INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A FCA-INPUT -p udp --sport 67 --dport 68 -j ACCEPT
iptables -A FCA-INPUT -s 10.0.1.0/24 -p tcp -m multiport --dports 22,443 -j ACCEPT
iptables -A FCA-INPUT -s 10.0.1.0/24 -p icmp -j ACCEPT
iptables -A FCA-INPUT -j DROP
iptables -C INPUT -j FCA-INPUT 2>/dev/null || iptables -I INPUT 1 -j FCA-INPUT
ip6tables -N FCA-INPUT 2>/dev/null || true
ip6tables -F FCA-INPUT
ip6tables -A FCA-INPUT -i lo -j ACCEPT
ip6tables -A FCA-INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
ip6tables -A FCA-INPUT -p ipv6-icmp -j ACCEPT
ip6tables -A FCA-INPUT -j DROP
ip6tables -C INPUT -j FCA-INPUT 2>/dev/null || ip6tables -I INPUT 1 -j FCA-INPUT
iptables -N DOCKER-USER 2>/dev/null || true
iptables -N FCA-FORWARD 2>/dev/null || true
iptables -F FCA-FORWARD
iptables -A FCA-FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
iptables -A FCA-FORWARD -i ens18 ! -s 10.0.1.0/24 -j DROP
iptables -A FCA-FORWARD -j RETURN
iptables -C DOCKER-USER -j FCA-FORWARD 2>/dev/null || iptables -I DOCKER-USER 1 -j FCA-FORWARD
EOF
chmod 0750 /usr/local/sbin/fca-firewall
cat > /etc/systemd/system/fca-firewall.service <<'EOF'
[Unit]
Description=FCA lab private-network firewall
Before=docker.service
After=network-pre.target
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/fca-firewall
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now fca-firewall
systemctl enable docker
sshd -t
sshd -T | grep -E '^(passwordauthentication|permitrootlogin|kbdinteractiveauthentication|pubkeyauthentication) '
docker version --format '{{.Server.Version}}'
docker compose version
findmnt /srv/fca/evidence
echo FCA_BOOTSTRAP_COMPLETE
