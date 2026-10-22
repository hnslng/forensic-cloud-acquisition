#!/usr/bin/env bash
# Run on a disposable Linux CI runner. No Proxmox access and no lab SSH credentials.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'if [[ -f "$WORK/qemu.pid" ]]; then kill "$(cat "$WORK/qemu.pid")" 2>/dev/null || true; fi; rm -rf "$WORK"' EXIT
cd "$ROOT"
python3 - "$WORK" <<'PY'
import json,sys,pathlib
lock=json.load(open('infrastructure/installer/debian13-amd64.lock.json'))['baseline_image']
p=pathlib.Path(sys.argv[1]);(p/'url').write_text(lock['url']);(p/'checksum').write_text(lock['sha512']+'  '+str(p/'base.qcow2')+'\n')
PY
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 "$(cat "$WORK/url")" -o "$WORK/base.qcow2"
sha512sum -c "$WORK/checksum"
qemu-img create -f qcow2 -F qcow2 -b "$WORK/base.qcow2" "$WORK/system.qcow2" 32G
qemu-img create -f qcow2 "$WORK/data.qcow2" 8G
ssh-keygen -q -t ed25519 -N '' -f "$WORK/ssh"
# Host key is supplied locally through cloud-init, never accepted from the network.
ssh-keygen -q -t ed25519 -N '' -f "$WORK/host"
printf '[127.0.0.1]:2222 %s\n' "$(cat "$WORK/host.pub")" > "$WORK/known_hosts"
python3 - "$WORK" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); private='\n'.join('    '+s for s in (p/'host').read_text().splitlines())
(p/'user-data').write_text('#cloud-config\ndisable_root: false\nssh_pwauth: false\nssh_keys:\n  ed25519_private: |\n'+private+'\n  ed25519_public: '+(p/'host.pub').read_text().strip()+'\nusers:\n  - name: root\n    ssh_authorized_keys:\n      - '+(p/'ssh.pub').read_text().strip()+'\nruncmd:\n  - touch /root/FCA_INSTALLER_DISPOSABLE_GUEST\n')
(p/'meta-data').write_text('instance-id: fca-installer-isolated\nlocal-hostname: fca-install-test\n')
PY
cloud-localds "$WORK/seed.iso" "$WORK/user-data" "$WORK/meta-data"
ACCEL=tcg
[[ ! -w /dev/kvm ]] || ACCEL=kvm
qemu-system-x86_64 -machine "accel=$ACCEL" -cpu max -m 3072 -smp 2 -display none -daemonize -pidfile "$WORK/qemu.pid" \
  -monitor none -serial "file:$WORK/serial.log" \
  -drive "file=$WORK/system.qcow2,if=virtio" -drive "file=$WORK/data.qcow2,if=none,id=fcadata" -device virtio-blk-pci,drive=fcadata,serial=FCAINSTALLTEST \
  -drive "file=$WORK/seed.iso,format=raw,if=virtio" \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-:22 -device virtio-net-pci,netdev=n0
SSH=(ssh -i "$WORK/ssh" -o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$WORK/known_hosts" -o ConnectTimeout=3 -p 2222 root@127.0.0.1)
SCP=(scp -q -i "$WORK/ssh" -o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$WORK/known_hosts" -P 2222)
for _ in $(seq 1 120); do
  if "${SSH[@]}" 'test -f /root/FCA_INSTALLER_DISPOSABLE_GUEST' 2>/dev/null; then break; fi
  sleep 5
done
"${SSH[@]}" 'test -f /root/FCA_INSTALLER_DISPOSABLE_GUEST'
git archive HEAD | "${SSH[@]}" 'mkdir /root/source; tar -x -C /root/source'
"${SSH[@]}" 'bash /root/source/tests/installer/fresh-debian.sh prepare'
"${SCP[@]}" -r root@127.0.0.1:/root/debs "$WORK/debs"
docker build --target runtime -t fca-install-ci:tested -f infrastructure/docker/Dockerfile .
APP_IMAGE=$(docker image inspect --format '{{.Id}}' fca-install-ci:tested)
openssl genpkey -algorithm ED25519 -out "$WORK/signing.key"
openssl pkey -in "$WORK/signing.key" -pubout -out "$WORK/trusted-release.pub"
python3 scripts/build_install_package.py --version 0.6.0-test.1 --output "$WORK/release" --debs "$WORK/debs" --signing-key "$WORK/signing.key" --trusted-key "$WORK/trusted-release.pub" --app-image "$APP_IMAGE"
"${SCP[@]}" "$WORK/trusted-release.pub" root@127.0.0.1:/root/trusted-release.pub
tar -C "$WORK/release" -cf - . | "${SSH[@]}" 'mkdir /root/release; tar -x -C /root/release'
"${SSH[@]}" 'bash /root/source/tests/installer/fresh-debian.sh install'
# Separate signed next version, no modification of the original package.
python3 scripts/build_install_package.py --version 0.6.0-test.2 --output "$WORK/release-next" --debs "$WORK/debs" --signing-key "$WORK/signing.key" --trusted-key "$WORK/trusted-release.pub" --app-image "$APP_IMAGE"
tar -C "$WORK/release-next" -cf - . | "${SSH[@]}" 'mkdir /root/release-next; tar -x -C /root/release-next'
"${SSH[@]}" 'bash /root/source/tests/installer/fresh-debian.sh update'
"${SSH[@]}" 'systemctl reboot' || true
sleep 10
for _ in $(seq 1 120); do
  if "${SSH[@]}" 'systemctl is-active --quiet fca' 2>/dev/null; then break; fi
  sleep 5
done
"${SSH[@]}" 'bash /root/source/tests/installer/fresh-debian.sh reboot-check'
