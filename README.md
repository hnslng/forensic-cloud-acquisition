# FORENSIC CLOUD ACQUISITION

Eigenständige, selbst gehostete Anwendung zur technischen Cloud-Datensicherung.
Entwicklung ausschließlich im privaten Testlabor mit synthetischen Daten und
ausdrücklich freigegebenen Testkonten. Keine Freigabe für echte Beweismittel.

## Tatsächlicher Stand

Phase 0 läuft. Proxmox wurde ausschließlich lesend geprüft. Das private
GitHub-Repository ist angelegt. **Eine VM wurde noch nicht erstellt: Die im
Projektauftrag verlangte Freigabe steht aus.** Es gibt noch keine Cloud-Adapter,
keine Benutzerverwaltung und keine nutzbare Webanwendung.

- [Prüfbericht und Freigabevorschlag](docs/phase-0-status.md)
- [Installationsablauf und Abnahme](docs/installation.md)
- [Architekturentwurf](docs/architecture.md)
- [Analyse der TRIAGE//BOX](docs/triagebox-reference.md)
- [Test- und Nachweisstand](docs/validation.md)
- [Änderungen](CHANGELOG.md)

## Vorhandene Werkzeuge

Python 3.11 oder neuer, Git und OpenSSH genügen für die lokale Prüfung:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/proxmox_inventory.py --host proxmox --output .local/proxmox-inventory.json
python3 scripts/check_vm_plan.py .local/proxmox-inventory.json infrastructure/proxmox/lab-plan.json
```

Der Inventarleser verwendet ausschließlich festgelegte Leseabfragen über einen
bereits eingerichteten SSH-Alias. Unbekannte Hostschlüssel werden abgewiesen.
Er verändert weder Proxmox-Konfiguration noch Gäste. Rohinventare bleiben lokal
und sind durch `.gitignore` ausgeschlossen.

`compose.yaml` stellt zunächst **nur PostgreSQL** für die spätere VM-Abnahme
bereit. Es veröffentlicht keinen Port. Die Ausführung erfolgt erst nach
Freigabe und Installation der VM; die Anwendungsdienste folgen in Phase 1.

## Projektstruktur

`backend/`, `frontend/`, `providers/{apple,google,microsoft}/`, `workers/`,
`database/`, `migrations/`, `infrastructure/{docker,proxmox}/`, `storage/`,
`tests/`, `scripts/` und `docs/` sind getrennte Verantwortungsbereiche.
Die jeweiligen README-Dateien kennzeichnen noch nicht implementierte Module.

Konfiguration und Geheimnisse liegen später unter `/etc/fca`, Datenbankdaten
unter `/var/lib/fca` und Testbeweisdaten auf einer separaten Disk unter
`/srv/fca/evidence`. Diese Verzeichnisse liegen außerhalb des Git-Checkouts.
Ein frei eingegebenes Bearbeiterkürzel ist niemals eine Zugriffsberechtigung.
