#!/usr/bin/env bash
# Run on a disposable Linux CI runner. No Proxmox access and no lab SSH credentials.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d)
FCA_INSTALL_MODE=${FCA_INSTALL_MODE:-offline}
[[ $FCA_INSTALL_MODE == offline || $FCA_INSTALL_MODE == bootstrap || $FCA_INSTALL_MODE == published || $FCA_INSTALL_MODE == short ]]
cleanup() {
  test_status=$?
  if [[ $test_status != 0 ]]; then
    for log in "$WORK/bios.log" "$WORK/serial.log"; do [[ ! -f "$log" ]] || tail -n 120 "$log"; done
  fi
  if [[ -f "$WORK/qemu.pid" ]]; then kill "$(cat "$WORK/qemu.pid")" 2>/dev/null || true; fi
  if [[ -n ${FIXTURE_PID:-} ]]; then sudo kill "$FIXTURE_PID" 2>/dev/null || true; fi
  rm -rf "$WORK"
}
trap cleanup EXIT
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
  -monitor none -serial "file:$WORK/serial.log" -boot order=c,strict=on \
  -chardev "file,id=bios,path=$WORK/bios.log" -device isa-debugcon,iobase=0x402,chardev=bios \
  -drive "file=$WORK/system.qcow2,if=none,id=fcasystem" -device virtio-blk-pci,drive=fcasystem,bootindex=1,serial=FCAINSTALLSYSTEM -drive "file=$WORK/data.qcow2,if=none,id=fcadata" -device virtio-blk-pci,drive=fcadata,serial=FCAINSTALLTEST \
  -drive "file=$WORK/seed.iso,format=raw,if=virtio" \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-:22 -device virtio-net-pci,netdev=n0
SSH=(ssh -i "$WORK/ssh" -o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$WORK/known_hosts" -o ConnectTimeout=2 -p 2222 root@127.0.0.1)
SCP=(scp -q -i "$WORK/ssh" -o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$WORK/known_hosts" -P 2222)
for _ in $(seq 1 30); do
  if "${SSH[@]}" 'test -f /root/FCA_INSTALLER_DISPOSABLE_GUEST' 2>/dev/null; then break; fi
  sleep 5
done
"${SSH[@]}" 'test -f /root/FCA_INSTALLER_DISPOSABLE_GUEST'
git archive HEAD | "${SSH[@]}" 'mkdir /root/source; tar -x -C /root/source'
"${SSH[@]}" "FCA_INSTALL_MODE=$FCA_INSTALL_MODE bash /root/source/tests/installer/fresh-debian.sh prepare"
if [[ $FCA_INSTALL_MODE == published || $FCA_INSTALL_MODE == short ]]; then
  "${SSH[@]}" 'mkdir /root/bootstrap'
  if [[ $FCA_INSTALL_MODE == short ]]; then
    "${SCP[@]}" releases/START-v1.txt root@127.0.0.1:/root/bootstrap/INSTALL.txt
    "${SSH[@]}" '! command -v docker && ! command -v nginx && test -z "${GH_TOKEN:-}${GITHUB_TOKEN:-}"'
    # Exercise the exact command on a minimal fresh guest without wget.
    "${SSH[@]}" 'apt-get -y remove wget && ! command -v wget'
  else
    "${SCP[@]}" releases/v0.6.0-rc.1/INSTALL.txt root@127.0.0.1:/root/bootstrap/INSTALL.txt
  fi
  "${SSH[@]}" 'cd /root/source && python3 tests/installer/run_bootstrap.py install && python3 tests/installer/seed_and_check.py seed && sha256sum /etc/fca/secrets/* > /root/secret-hashes && python3 scripts/fca_admin.py backup && python3 tests/installer/seed_and_check.py restore-check'
  "${SSH[@]}" 'systemctl reboot' || true
  sleep 10
  for _ in $(seq 1 30); do
    if "${SSH[@]}" 'systemctl is-active --quiet fca' 2>/dev/null; then break; fi
    sleep 5
  done
  "${SSH[@]}" 'bash /root/source/tests/installer/fresh-debian.sh reboot-check && echo FRESH_DEBIAN_PUBLIC_GITHUB_SIGNED_RELEASE_PASS'
  if [[ $FCA_INSTALL_MODE == short ]]; then
    "${SSH[@]}" 'test -z "$(lsblk -n -o FSTYPE /dev/disk/by-id/virtio-FCAINSTALLTEST)" && echo FRESH_DEBIAN_SHORT_VERIFIED_STARTER_PASS'
  fi
  exit 0
fi
"${SCP[@]}" -r root@127.0.0.1:/root/debs "$WORK/debs"
docker build --target runtime -t fca-install-ci:tested -f infrastructure/docker/Dockerfile .
APP_IMAGE=$(docker image inspect --format '{{.Id}}' fca-install-ci:tested)
openssl genpkey -algorithm ED25519 -out "$WORK/signing.key"
openssl pkey -in "$WORK/signing.key" -pubout -out "$WORK/trusted-release.pub"
python3 scripts/build_install_package.py --version 0.6.0-test.1 --archive "$WORK/fca-0.6.0-test.1.tar.gz" --output "$WORK/release" --debs "$WORK/debs" --signing-key "$WORK/signing.key" --trusted-key "$WORK/trusted-release.pub" --app-image "$APP_IMAGE"
if [[ $FCA_INSTALL_MODE == bootstrap ]]; then
  python3 scripts/build_bootstrap.py --version 0.6.0-test.1 --archive "$WORK/fca-0.6.0-test.1.tar.gz" --trusted-key "$WORK/trusted-release.pub" --output "$WORK/bootstrap"
  FIXTURE="$WORK/fixture/hnslng/forensic-cloud-acquisition/releases/download/v0.6.0-test.1"
  mkdir -p "$FIXTURE"
  cp "$WORK/fca-0.6.0-test.1.tar.gz"* "$FIXTURE/"
  cp "$WORK/bootstrap/fca-bootstrap.py" "$FIXTURE/"
  openssl req -x509 -newkey rsa:2048 -nodes -keyout "$WORK/fixture-ca.key" -out "$WORK/fixture-ca.pem" -subj /CN=Disposable-HTTPS-fixture -days 2 -addext 'basicConstraints=critical,CA:TRUE' -addext 'keyUsage=critical,keyCertSign,cRLSign' >/dev/null 2>&1
  openssl req -newkey rsa:2048 -nodes -keyout "$WORK/fixture.key" -out "$WORK/fixture.csr" -subj /CN=github.com >/dev/null 2>&1
  printf '%s\n' 'basicConstraints=critical,CA:FALSE' 'keyUsage=critical,digitalSignature,keyEncipherment' 'extendedKeyUsage=serverAuth' 'subjectAltName=DNS:github.com' > "$WORK/fixture.ext"
  openssl x509 -req -in "$WORK/fixture.csr" -CA "$WORK/fixture-ca.pem" -CAkey "$WORK/fixture-ca.key" -CAcreateserial -out "$WORK/fixture.pem" -days 2 -extfile "$WORK/fixture.ext" >/dev/null 2>&1
  sudo python3 tests/installer/release_fixture_server.py "$WORK/fixture" "$WORK/fixture.pem" "$WORK/fixture.key" &
  FIXTURE_PID=$!
  "${SCP[@]}" "$WORK/fixture-ca.pem" root@127.0.0.1:/root/fixture-ca.pem
  "${SCP[@]}" -r "$WORK/bootstrap" root@127.0.0.1:/root/bootstrap
  # Isolated guest only: genuine HTTPS requests use a controlled release fixture.
  # The production bootstrap and generated install command are not modified.
  "${SSH[@]}" "echo '10.0.2.2 github.com' >> /etc/hosts"
fi
openssl pkeyutl -verify -pubin -inkey "$WORK/trusted-release.pub" -rawin -in "$WORK/fca-0.6.0-test.1.tar.gz.sha256" -sigfile "$WORK/fca-0.6.0-test.1.tar.gz.sha256.sig"
(cd "$WORK"
 sha256sum -c fca-0.6.0-test.1.tar.gz.sha256)
mkdir "$WORK/unpacked"
tar -xzf "$WORK/fca-0.6.0-test.1.tar.gz" -C "$WORK/unpacked"
"${SCP[@]}" "$WORK/trusted-release.pub" root@127.0.0.1:/root/trusted-release.pub
tar -C "$WORK/unpacked/fca-0.6.0-test.1" -cf - . | "${SSH[@]}" 'mkdir /root/release; tar -x -C /root/release'
"${SSH[@]}" "FCA_INSTALL_MODE=$FCA_INSTALL_MODE bash /root/source/tests/installer/fresh-debian.sh install"
# Separate signed next version, no modification of the original package.
python3 scripts/build_install_package.py --version 0.6.0-test.2 --output "$WORK/release-next" --debs "$WORK/debs" --signing-key "$WORK/signing.key" --trusted-key "$WORK/trusted-release.pub" --app-image "$APP_IMAGE"
tar -C "$WORK/release-next" -cf - . | "${SSH[@]}" 'mkdir /root/release-next; tar -x -C /root/release-next'
"${SSH[@]}" 'bash /root/source/tests/installer/fresh-debian.sh update'
# A signed but deliberately unhealthy candidate must fall back without data restore.
python3 - "$WORK" <<'PYBAD'
import json,pathlib,shutil,subprocess,sys
from infrastructure.installer.package import write_manifest
p=pathlib.Path(sys.argv[1]); source=p/'release-next'; bad=p/'release-bad'
shutil.copytree(source,bad)
compose=json.loads((bad/'compose.template.json').read_text())
compose['services']['api']['healthcheck']={'test':['CMD','python','-c','raise SystemExit(1)'],'interval':'1s','timeout':'1s','retries':1,'start_period':'0s'}
(bad/'compose.template.json').write_text(json.dumps(compose))
m=json.loads((source/'manifest.json').read_text())
write_manifest(bad,'0.6.0-test.3',m['app_image'],m['database_image'],m['dependencies'],m['source_revision'])
subprocess.check_call(['openssl','pkeyutl','-sign','-inkey',str(p/'signing.key'),'-rawin','-in',str(bad/'manifest.json'),'-out',str(bad/'manifest.sig')])
PYBAD
tar -C "$WORK/release-bad" -cf - . | "${SSH[@]}" 'mkdir /root/release-bad; tar -x -C /root/release-bad'
"${SSH[@]}" 'bash /root/source/tests/installer/fresh-debian.sh failed-update'
"${SSH[@]}" 'systemctl reboot' || true
sleep 10
for _ in $(seq 1 30); do
  if "${SSH[@]}" 'systemctl is-active --quiet fca' 2>/dev/null; then break; fi
  sleep 5
done
"${SSH[@]}" 'bash /root/source/tests/installer/fresh-debian.sh reboot-check'
if [[ $FCA_INSTALL_MODE == bootstrap && -n ${FCA_RELEASE_OUTPUT:-} ]]; then
  mkdir -p "$FCA_RELEASE_OUTPUT"
  cp "$WORK/fca-0.6.0-test.1.tar.gz"* "$WORK/trusted-release.pub" "$FCA_RELEASE_OUTPUT/"
  cp "$WORK/bootstrap/"* "$FCA_RELEASE_OUTPUT/"
  git rev-parse HEAD > "$FCA_RELEASE_OUTPUT/source-revision.txt"
  # Only the disposable public test key is exported. Private key is destroyed.
fi
