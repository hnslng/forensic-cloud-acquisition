"""Synthetic capacity regression tests; these do not prove VM operation."""

import copy
import unittest
from unittest.mock import patch

from scripts.check_vm_plan import GIB, check_plan
from scripts.proxmox_inventory import collect


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.plan = dict(vmid=105, vcpus=2, memory_mib=2048,
                         host_memory_reserve_mib=1536, system_disk_gib=32,
                         data_disk_gib=32, storage_reserve_gib=24,
                         storage="local-lvm", bridge="vmbr0")
        values = {
            "nodes": [dict(node="lab", maxcpu=4, maxmem=8 * GIB)],
            "guests": [dict(vmid=100, maxmem=2 * GIB, status="running")],
            "memory": "MemTotal: 8388608 kB\nMemAvailable: 4194304 kB\n",
            "storage": [dict(storage="local-lvm", active=1, content="images,rootdir", avail=98 * GIB)],
            "network": [dict(iface="vmbr0", type="bridge", active=1)],
        }
        self.inventory = dict(node="lab", queries={k: {"data": v} for k, v in values.items()})

    def test_small_lab_fits_with_reserves(self):
        self.assertEqual(check_plan(self.inventory, self.plan), [])

    def test_requested_eight_gib_would_exhaust_host(self):
        self.plan["memory_mib"] = 8192
        self.assertTrue(any("RAM" in p for p in check_plan(self.inventory, self.plan)))

    def test_eighty_gib_plus_data_exceeds_storage_reserve(self):
        self.plan["system_disk_gib"] = 80
        self.assertTrue(any("Speicher" in p for p in check_plan(self.inventory, self.plan)))

    def test_occupied_id_is_rejected(self):
        self.inventory["queries"]["guests"]["data"].append(dict(vmid=105))
        self.assertIn("VM-ID ist bereits belegt.", check_plan(self.inventory, self.plan))

    def test_inactive_bridge_is_rejected(self):
        self.inventory["queries"]["network"]["data"][0]["active"] = 0
        self.assertIn("Aktive Netzwerkbrücke fehlt.", check_plan(self.inventory, self.plan))

    def test_inactive_storage_is_rejected(self):
        self.inventory["queries"]["storage"]["data"][0]["active"] = 0
        self.assertIn("Aktiver VM-Storage fehlt.", check_plan(self.inventory, self.plan))

    def test_memory_assigned_to_running_guests_is_reserved(self):
        self.inventory["queries"]["guests"]["data"][0]["maxmem"] = 6 * GIB
        self.assertTrue(any("laufende Gäste" in p for p in check_plan(self.inventory, self.plan)))

    def test_missing_or_failed_query_does_not_look_successful(self):
        for name in ("nodes", "guests", "memory", "storage", "network"):
            with self.subTest(name=name):
                broken = copy.deepcopy(self.inventory)
                broken["queries"][name] = {"error": "timeout"}
                self.assertEqual(check_plan(broken, self.plan), [f"Pflichtabfrage fehlt: {name}"])

    def test_missing_memory_available_does_not_look_successful(self):
        self.inventory["queries"]["memory"]["data"] = "MemTotal: 8388608 kB\n"
        self.assertEqual(check_plan(self.inventory, self.plan), ["Verfügbarer Arbeitsspeicher wurde nicht erhoben."])

    def test_excess_cpu_is_rejected(self):
        self.plan["vcpus"] = 5
        self.assertIn("CPU-Anforderung passt nicht zum Host.", check_plan(self.inventory, self.plan))


class InventorySafetyTests(unittest.TestCase):
    @patch("scripts.proxmox_inventory.subprocess.run")
    def test_option_or_command_injection_never_reaches_ssh(self, run):
        for host in ("-oProxyCommand=evil", "proxmox;reboot", "proxmox\nreboot", "root@host"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                collect(host)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
