# Abnahme des Paketinstallers

Entwicklungsstand: `codex/install-update`, Paketformat 1, Debian 13 amd64,
Datenbankschema 9. Noch keine produktiv freigegebene Releaseversion.

## Automatisierte Prüfungen

- `python3 -m unittest discover -s tests -p test_installer.py -v`:
  Signatur, falscher Schlüssel, manipulierte/fehlende/zusätzliche Dateien,
  Linkangriffe, verbotene öffentliche Adressen, Konfigurationsinjektion,
  Sicherungs-/Backuppfadtrennung, fehlender/falscher Datenträger, Wiederholung.
- Bisherige Infrastrukturtests bleiben Bestandteil der Abnahme.
- Bestehender Backend-/Browser-/iCloud-CI-Ablauf bleibt erhalten.

## Vollständig frische Debian-Umgebung

Workflow `.github/workflows/installer.yml`, Skript `scripts/test_fresh_debian.sh`:
Eigene wegwerfbare QEMU-VM auf einem GitHub-Runner, datiertes offizielles
Debian-13-Cloudimage mit festgeschriebenem SHA-512, neue Systemdisk und eindeutig
benannte neue Testdatendisk. Keine Zugangsdaten zur FCA-VM oder zu Proxmox.

Geprüft werden Erstinstallation ohne vorhandenen Docker/nginx, Wiederholung,
signiertes Update auf zweite Version, Erhalt synthetischer Daten und Schlüssel,
Datenbank-Restoreprobe und gesicherte Dateiinhalte, fehlender Datenträger sowie
VM-Neustart mit erneutem Dienste-/Persistenztest. Signierschlüssel und CA sind
ausschließlich kurzlebige Testschlüssel. Keine echten Cloud-Konten.

Das Cloudimage wird gegen den über Debian-HTTPS ermittelten, im Repository
festgeschriebenen SHA-512 geprüft. Das ist keine zusätzliche unabhängige
Debian-Imagesignatur. APT verifiziert auf dem Releasebuilder signierte
Debian-Metadaten. Der resultierende vollständige .deb-Satz erhält nochmals
SHA-256-Werte und die FCA-Releasesignatur.

## Ergebnis

Die tatsächlichen CI-Ergebnisse werden nach dem Lauf ergänzt. Ein angelegter
Workflow oder ein Unit-Test ist **kein** Nachweis einer erfolgreichen
Serverinstallation. Bestehende FCA-Test-VM und andere Proxmox-Gäste werden für
diese Phase nicht verändert.
