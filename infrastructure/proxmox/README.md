`lab-plan.json` wurde am 21.10.2026 ausdrücklich freigegeben und auf VM 105
umgesetzt. `create-vm-105.sh` prüft Ressourcen und verweigert vorhandene IDs
oder Disks. Es verändert keine vorhandenen Gäste oder Host-Einstellungen.
`prepare_cloud_init.py` erzeugt aus einem öffentlichen Schlüssel ein NoCloud-
Seed außerhalb von Git. Ein erneuter Aufruf ist keine Updatefunktion und
darf nicht über die bestehende Installation ausgeführt werden.
