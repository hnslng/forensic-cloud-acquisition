#!/bin/bash
# Execute on the approved Proxmox host only. Never modifies existing guests.
set -euo pipefail
test "${FCA_VM105_APPROVED:-}" = yes
test "$(hostname)" = pve
test ! -e /etc/pve/qemu-server/105.conf
test ! -e /etc/pve/lxc/105.conf
test -f /var/lib/vz/fca-105/seed/user-data
test -f /var/lib/vz/fca-105/seed/meta-data
test -f /var/lib/vz/fca-105/seed/network-config
test "$(pvesm list local-lvm --vmid 105 | wc -l)" -eq 1
available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
test "$available_kib" -ge 3670016
python3 - <<'PY'
import json, subprocess
stores=json.loads(subprocess.check_output(['pvesh','get','/nodes/pve/storage','--output-format','json']))
store=next(s for s in stores if s['storage']=='local-lvm')
assert store['active'] and store['avail'] >= 88*1024**3
PY
image=debian-13-genericcloud-amd64-20261017-2634.qcow2
base=https://cloud.debian.org/images/cloud/trixie/20261017-2634
cd /var/lib/vz/fca-105
curl --fail --show-error --silent --location --proto '=https' --tlsv1.2 "$base/SHA512SUMS" -o SHA512SUMS
curl --fail --show-error --silent --location --proto '=https' --tlsv1.2 "$base/$image" -o "$image"
awk -v image="$image" '$2 == image || $2 == "*" image {print}' SHA512SUMS > image.sha512
test "$(wc -l < image.sha512)" -eq 1
sha512sum --check image.sha512
sha256sum "$image" > image.sha256
curl --fail --show-error --silent --location --proto '=https' --tlsv1.2 "$base/debian-13-genericcloud-amd64-20261017-2634.json" -o image-metadata.json
qemu-img info "$image"
genisoimage -quiet -output /var/lib/vz/template/iso/fca-105-seed.iso -volid cidata -joliet -rock seed/user-data seed/meta-data seed/network-config
qm create 105 --name forensic-cloud-acquisition --cores 2 --memory 2048 --balloon 0 \
  --cpu x86-64-v2-AES --net0 virtio=BC:24:11:FA:01:05,bridge=vmbr0 \
  --scsihw virtio-scsi-single --serial0 socket --vga serial0 \
  --agent enabled=1 --onboot 1 --startup order=50,up=30,down=90 --ostype l26
qm importdisk 105 "$image" local-lvm --format raw
qm set 105 --scsi0 local-lvm:vm-105-disk-0,discard=on,ssd=1,iothread=1,serial=FCA105SYSTEM
qm resize 105 scsi0 32G
qm set 105 --scsi1 local-lvm:32,discard=on,ssd=1,iothread=1,serial=FCA105EVIDENCE
qm set 105 --ide2 local:iso/fca-105-seed.iso,media=cdrom
# Set boot order after all device mutations (Proxmox may recalculate it).
qm set 105 --boot order=scsi0
qm config 105 | grep -Fx 'boot: order=scsi0'
qm config 105
qm start 105
