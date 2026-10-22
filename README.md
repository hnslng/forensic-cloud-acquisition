# FORENSIC CLOUD ACQUISITION

Eigenständige, selbst gehostete Anwendung zur technischen Cloud-Datensicherung.
Entwicklung ausschließlich im privaten Testlabor mit synthetischen Daten und
ausdrücklich freigegebenen Testkonten. Keine Freigabe für echte Beweismittel.

## Installation auf einer neuen Debian-13-VM

Als **root** den gesamten Befehl kopieren. Er lädt das kleine Startskript aus diesem Repository, prüft dessen fest vorgegebenen SHA-256-Wert und startet anschließend den bestehenden sicheren Bootstrap:

```sh
(apt-get update && apt-get install -y wget=1.25.0-2 ca-certificates=20250419 &&
 cd "$(mktemp -d)" &&
 wget -qO start.sh https://raw.githubusercontent.com/hnslng/forensic-cloud-acquisition/installer-v1/start.sh &&
 echo "5df46ffd45b36a71e38be7b720b0bbf2ab37ae42e147866fc8233e5c2e31e967  start.sh" | sha256sum -c - &&
 bash start.sh)
```

Der Aufruf richtet **FCA v0.6.0-rc.1** interaktiv ein und zeigt anschließend die HTTPS-Webadresse. Kein GitHub-Konto oder persönlicher Token erforderlich. Die Paket- und Signaturprüfungen bleiben vollständig erhalten; Datenträger werden nicht formatiert. Der bestehende [Offlineinstaller](docs/installation.md) bleibt verfügbar.

**Vertrauen:** Den Befehl einschließlich Prüfsumme aus einer unabhängig freigegebenen Kopie dieser Anleitung übernehmen und den Prüfwert nicht durch eine gleichzeitig heruntergeladene Prüfsummendatei ersetzen. Der kurze Aufruf benötigt einen öffentlichen Zugriff auf Repository und Release. Die Sichtbarkeit ändert ausschließlich der Eigentümer.

[Details zur Installation](docs/bootstrap-installation.md) · [Kopierbarer Aufruf](releases/START-v1.txt)

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

- [Stufe B: Entwicklungsstand, Stabilität und offene Abnahme](docs/stufe-b-status.md)
- [Privates HTTPS und erster Google-/Microsoft-Test](docs/private-https-oauth.md)
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
- [Paketinstallation auf Debian 13](docs/installation.md)
- [Installer-Abnahme in frischer Debian-VM](docs/installer-tests.md)
- [Backup, Wiederherstellung und Rollback](docs/backup-restore-rollback.md)
- [Versionierte Releases und Behördeninstallation](docs/release-packages.md)
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

### Installation über ein freigegebenes GitHub-Release

Der [Bootstrap-Installer](docs/bootstrap-installation.md) verwendet eine feste, signierte Releaseversion aus diesem Repository. Kein GitHub-Konto am Zielserver erforderlich. Anonyme Downloads setzen ein öffentliches Repository und ein veröffentlichtes Release voraus; die Sichtbarkeit ändert ausschließlich der Eigentümer. Der bestehende Offlineinstaller bleibt verfügbar.

Geprüfter Installationskandidat: [v0.6.0-rc.1](https://github.com/hnslng/forensic-cloud-acquisition/releases/tag/v0.6.0-rc.1). [Exakter Ein-Befehl-Start](releases/v0.6.0-rc.1/INSTALL.txt) · [Testergebnisse](docs/bootstrap-tests.md).
