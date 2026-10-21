#!/usr/bin/env python3
"""Evaluate capacity conservatively; never provision or grant approval."""

import argparse
import json
from pathlib import Path

MIB = 1024**2
GIB = 1024**3


def check_plan(inventory, plan):
    queries = inventory["queries"]
    for name in ("nodes", "guests", "memory", "storage", "network"):
        if name not in queries or "data" not in queries[name]:
            return [f"Pflichtabfrage fehlt: {name}"]
    problems = []
    node = next((n for n in queries["nodes"]["data"] if n["node"] == inventory["node"]), None)
    if node is None:
        return ["Hostdaten fehlen."]
    if plan["vcpus"] < 1 or plan["vcpus"] > node["maxcpu"]:
        problems.append("CPU-Anforderung passt nicht zum Host.")
    memory = {}
    for line in queries["memory"]["data"].splitlines():
        key, _, value = line.partition(":")
        if key in ("MemTotal", "MemAvailable"):
            memory[key] = int(value.split()[0]) * 1024
    if "MemAvailable" not in memory:
        return ["Verfügbarer Arbeitsspeicher wurde nicht erhoben."]
    required_memory = (plan["memory_mib"] + plan["host_memory_reserve_mib"]) * MIB
    if plan["memory_mib"] < 1 or required_memory > memory["MemAvailable"]:
        problems.append("Zu wenig verfügbarer RAM einschließlich Hostreserve.")
    guests = queries["guests"]["data"]
    if any(int(g["vmid"]) == plan["vmid"] for g in guests):
        problems.append("VM-ID ist bereits belegt.")
    assigned = sum(g.get("maxmem", 0) for g in guests if g.get("status") == "running")
    if assigned + required_memory > node["maxmem"]:
        problems.append("Konfigurierte laufende Gäste lassen zu wenig RAM-Reserve.")
    storage = next((s for s in queries["storage"]["data"] if s["storage"] == plan["storage"]), None)
    if not storage or not storage.get("active") or "images" not in storage.get("content", "").split(","):
        problems.append("Aktiver VM-Storage fehlt.")
    else:
        required_disk = plan["system_disk_gib"] + plan["data_disk_gib"] + plan["storage_reserve_gib"]
        if min(plan["system_disk_gib"], plan["data_disk_gib"]) <= 0 or required_disk * GIB > storage["avail"]:
            problems.append("Zu wenig physischer Speicher einschließlich Reserve.")
    if not any(n["iface"] == plan["bridge"] and n.get("type") == "bridge" and n.get("active") for n in queries["network"]["data"]):
        problems.append("Aktive Netzwerkbrücke fehlt.")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        problems = check_plan(json.loads(args.inventory.read_text()), json.loads(args.plan.read_text()))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Prüfung unvollständig: {type(exc).__name__}")
        return 2
    for problem in problems:
        print("NICHT GEEIGNET: " + problem)
    if not problems:
        print("Ressourcenprüfung bestanden. Momentaufnahme; keine Reservierung oder Freigabe.")
        print("Gestoppte Gäste und Snapshot-Wachstum sind zusätzlich zu berücksichtigen.")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
