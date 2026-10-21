#!/usr/bin/env python3
"""Guest-only capacity observation; never logs environment variables/secrets."""
from datetime import datetime, timezone
import json
import os
import shutil
import subprocess


def snapshot():
    memory = {}
    with open('/proc/meminfo') as handle:
        for line in handle:
            key, _, value = line.partition(':')
            if key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
                memory[key] = int(value.split()[0]) * 1024
    filesystems = {}
    for path in ('/', '/var/lib/fca', '/srv/fca/evidence'):
        if os.path.exists(path):
            usage = shutil.disk_usage(path)
            filesystems[path] = dict(total=usage.total, used=usage.used, free=usage.free,
                                     is_mount=os.path.ismount(path))
    result = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}'],
                            capture_output=True, text=True, timeout=20)
    return dict(at=datetime.now(timezone.utc).isoformat(), memory_bytes=memory,
                filesystems=filesystems,
                containers=[json.loads(l) for l in result.stdout.splitlines()] if result.returncode == 0 else [])


if __name__ == '__main__':
    print(json.dumps(snapshot(), indent=2))
