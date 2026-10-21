# FORENSIC CLOUD ACQUISITION

Eigenständige, selbst gehostete Anwendung zur technischen Cloud-Datensicherung.
Entwicklung ausschließlich im privaten Testlabor mit synthetischen Daten und
ausdrücklich freigegebenen Testkonten. Keine Freigabe für echte Beweismittel.

## Tatsächlicher Stand

Phase 0 ist nach Freigabe erfolgreich auf VM 105 umgesetzt und praktisch
abgenommen, einschließlich VM-Neustart, PostgreSQL-Persistenz und Restore.
**Phase 1 ist umgesetzt:** privates HTTPS, persönliche Anmeldung, Benutzer- und
Fallverwaltung mit serverseitigen Rechten und Audit. Die Oberfläche folgt dem
TRIAGE//BOX-Start-/Fallablauf in der freigegebenen dunkelblauen Gestaltung und
verwaltet mehrere benannte
Cloud-Konten je Fall. **Version 0.5.0 implementiert tatsächliche Sicherungen:**
iCloud Drive/Fotos sowie offizielle Google-Drive-/Kalender- und Microsoft-OneDrive-/Outlook-Kalender-Adapter, eine dauerhafte Warteschlange,
parallele Übertragungen, Wiederaufnahme auf Dateiebene, SHA-256 und Sicherungsberichte.
Echtkonto-Abnahmen stehen aus; Google/Microsoft benötigen registrierte Anbieteranwendungen.
Nicht verfügbare Kategorien und Bereichsgrenzen sind ausdrücklich dokumentiert.

- [Stufe A: Google-/OneDrive-Machbarkeit und Freigabeentscheidung](docs/stufe-a-machbarkeit.md)
- [Kurzanleitung: Fall anlegen und sichern](docs/kurzanleitung.md)
- [Prüfungen, Datenerhalt, Ressourcen und Bereitstellung 0.5.0](docs/cloud-acquisition-validation.md)
- [Cloud-Sicherungen: Anbieterstatus und Grenzen](docs/cloud-acquisition.md)
- [Abschlussbericht Phase 0 und Ressourcenverbrauch](docs/phase-0-completion.md)
- [Umsetzung und Abnahme Phase 1](docs/phase-1-status.md)
- [Phase 2: iCloud-Anmeldung, Grenzen und Abnahme](docs/phase-2-icloud.md)
- [Verbindliches finales UI und Abnahme](docs/final-ui-acceptance.md)
- [Historische Layoutüberarbeitung für Lesbarkeit und Desktopproportionen](docs/ui-layout-refinement.md)
- [Vergleich mit dem tatsächlichen TRIAGE//BOX-Frontend](docs/ui-triagebox-comparison.md)
- [Laborzugang und Administration](docs/operation.md)

- [Prüfbericht und Freigabevorschlag](docs/phase-0-status.md)
- [Installationsablauf und Abnahme](docs/installation.md)
- [Aktuelle Architektur](docs/architecture.md)
- [Analyse der TRIAGE//BOX](docs/triagebox-reference.md)
- [Test- und Nachweisstand](docs/validation.md)
- [Änderungen](CHANGELOG.md)

## Vorhandene Werkzeuge

Python 3.11 oder neuer, Git und OpenSSH genügen für die lokale Prüfung:

```sh
python3 -m unittest discover -s tests -p test_infrastructure.py -v
python3 scripts/proxmox_inventory.py --host proxmox --output .local/proxmox-inventory.json
python3 scripts/check_vm_plan.py .local/proxmox-inventory.json infrastructure/proxmox/lab-plan.json
```

Der Inventarleser verwendet ausschließlich festgelegte Leseabfragen über einen
bereits eingerichteten SSH-Alias. Unbekannte Hostschlüssel werden abgewiesen.
Er verändert weder Proxmox-Konfiguration noch Gäste. Rohinventare bleiben lokal
und sind durch `.gitignore` ausgeschlossen.

`compose.yaml` stellt PostgreSQL und über das Profil `application` die API
bereit. Nur der API-Port wird an Loopback der VM gebunden. Der Debian-nginx-
Dienst liefert das getrennte Frontend über privates HTTPS. Reale VM- und
Restoretests sind dokumentiert. Der isolierte Anwendungstestlauf umfasst
PostgreSQL-Integration und echte Chromium-Bedienabläufe.

## Projektstruktur

`backend/`, `frontend/`, `providers/{apple,google,microsoft}/`, `workers/`,
`database/`, `migrations/`, `infrastructure/{docker,proxmox}/`, `storage/`,
`tests/`, `scripts/` und `docs/` sind getrennte Verantwortungsbereiche.
Die jeweiligen README-Dateien kennzeichnen noch nicht implementierte Module.

Konfiguration und Geheimnisse liegen später unter `/etc/fca`, Datenbankdaten
unter `/var/lib/fca` und Testbeweisdaten auf einer separaten Disk unter
`/srv/fca/evidence`. Diese Verzeichnisse liegen außerhalb des Git-Checkouts.
Ein frei eingegebenes Bearbeiterkürzel ist niemals eine Zugriffsberechtigung.
