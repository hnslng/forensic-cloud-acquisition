#!/usr/bin/env python3
"""Read-only inventory via an existing SSH alias; output contains no credentials."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

# This program is sent over SSH stdin. All remote commands are fixed read queries.
REMOTE_PROGRAM = r'''
import json, socket, subprocess
node = socket.gethostname()
commands = {
    "version": ["pveversion"],
    "nodes": ["pvesh", "get", "/cluster/resources", "--type", "node", "--output-format", "json"],
    "guests": ["pvesh", "get", "/cluster/resources", "--type", "vm", "--output-format", "json"],
    "nextid": ["pvesh", "get", "/cluster/nextid", "--output-format", "json"],
    "storage": ["pvesh", "get", "/nodes/" + node + "/storage", "--output-format", "json"],
    "network": ["pvesh", "get", "/nodes/" + node + "/network", "--output-format", "json"],
    "local_content": ["pvesh", "get", "/nodes/" + node + "/storage/local/content", "--output-format", "json"],
    "memory": ["cat", "/proc/meminfo"],
    "cpu": ["lscpu", "--json"],
    "backup_jobs": ["pvesh", "get", "/cluster/backup", "--output-format", "json"],
}
results = {}
for name, command in commands.items():
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if result.returncode:
            results[name] = {"error": "read command failed", "returncode": result.returncode}
        else:
            try:
                results[name] = {"data": json.loads(result.stdout)}
            except json.JSONDecodeError:
                results[name] = {"data": result.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired):
        results[name] = {"error": "read command unavailable or timed out"}
print(json.dumps({"node": node, "queries": results}))
'''


def collect(host):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", host):
        raise ValueError("Ein eingerichteter SSH-Alias ist erforderlich.")
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
         "-o", "ConnectTimeout=10", host, "python3", "-"],
        input=REMOTE_PROGRAM, capture_output=True, text=True, timeout=360, check=True,
    )
    data = json.loads(result.stdout)
    data["collected_at"] = datetime.now(timezone.utc).isoformat()
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="proxmox")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = collect(args.host)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids overwriting existing inventory or following symlinks.
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    failures = [key for key, value in data["queries"].items() if "error" in value]
    print(f"Inventar gespeichert: {args.output}; fehlgeschlagene Abfragen: {len(failures)}")
    if failures:
        print("Nicht erhoben: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
