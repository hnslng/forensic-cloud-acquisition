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

Der Testablauf umfasst Erstinstallation ohne vorhandenen Docker/nginx und ohne
Internetrouting, kontrolliert fehlgeschlagenen Paketmanager-Aufruf und Fortsetzen
mit unveränderten Schlüsseln, wiederholte Installation, HTTPS-Startseite und
Administratoranmeldung, signiertes Update auf zweite Version, expliziten
Programmrollback und einen absichtlich fehlerhaften Updatekandidaten.
Synthetischer Fall, Benutzer, Fallrecht, Cloud-Konto, verschlüsselter
Cloud-Eintrag, Audit und manuell pausierter Auftrag müssen erhalten bleiben.
Datenbank-Restoreprobe einschließlich Besitzern/Rechten, gesicherte Dateiinhalte,
fehlender Datenträger und VM-Neustart schließen den Ablauf ab. Signierschlüssel und CA sind
ausschließlich kurzlebige Testschlüssel. Keine echten Cloud-Konten.

Das Cloudimage wird gegen den über Debian-HTTPS ermittelten, im Repository
festgeschriebenen SHA-512 geprüft. Das ist keine zusätzliche unabhängige
Debian-Imagesignatur. APT verifiziert auf dem Releasebuilder signierte
Debian-Metadaten. Der resultierende vollständige .deb-Satz erhält nochmals
SHA-256-Werte und die FCA-Releasesignatur.

## Ergebnis und reproduzierbare Nachweise

Der Lauf des vollständigen Anwendungs-/Betriebsstands
`b7a98f9f7e048400ea777f1ca62a31c2d61cacdd` ist erfolgreich:

- [Debian-Neuinstallation, Update, Restore, Rollback und Neustart](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39713522225)
- [Backend, Chromium und iCloud-Regressionen](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39713522130)
- [Maschinenlesbarer Nachweis mit Quelldatei-Prüfsummen](test-results/installer-validation.json)

| Prüfung | Nachgewiesenes Ergebnis |
|---|---|
| Installer-Sicherheitsverträge | 29 in der genannten CI bestanden |
| Versions-/Wheelhash-Synchronität | 2 bestanden |
| Infrastrukturverträge | 11 bestanden |
| Backend / PostgreSQL | 73 bestanden |
| Chromium-Bedienabläufe | 10 bestanden |
| iCloud-Offlineverträge | 10 bestanden |
| Vollständig frische Debian-13-VM | gesamter Lebenszyklus bestanden |
| Wiederhergestellter Fall, Datei und Cloud-Vault im echten Backend | bestanden |

Zusätzlich wurde die Release-Dateiauswahl gehärtet: Nur versionierte Dateien
werden übernommen; ignorierte Zugangsdaten und unversionierte Testreste bleiben
außerhalb des Pakets. Dafür ist eine weitere lokale Prüfung bestanden
(**30 Installerprüfungen insgesamt**). Die abschließende Paketbau-CI einschließlich
dieser Ergänzung ist unter den [aktuellen PR-Prüfungen](https://github.com/hnslng/forensic-cloud-acquisition/pull/2/checks)
verlinkt. Der PR wird erst nach deren Erfolg als fertig gemeldet.

Es wurden 15 FCA-Tabellen plus eine synthetische Prüftabelle über Zeilenzeugen
verglichen. Zwei Benutzer, ein Fall, eine Fallzuordnung, ein Cloud-Konto, Audit,
ein manuell pausierter Auftrag und die verschlüsselte Kontoablage blieben erhalten.
Alle fünf Passwort-/Schlüsseldateien wurden per SHA-256 vor/nach verglichen.
Die gesicherte Datei umfasst 24.576 synthetische Bytes. Nach dem Restore sind
Tabellenbesitzer `fca_migrate` und die Leserechte von `fca_api` nachgewiesen.

### Ressourcen der isolierten Installation

Testkonfiguration: 2 vCPU, 3 GiB zugewiesener RAM, 32-GiB-Systemdisk,
8-GiB-Testdatendisk. Nach dem letzten Neustart:

- ungefähr **456 MiB** aus `MemTotal − MemAvailable`; etwa **2,46 GiB verfügbar**;
- ungefähr **23,92 GiB** freier Systemspeicher einschließlich drei aufbewahrter
  Testversionen, Images und Paketcache;
- ungefähr **7,76 GiB** frei auf dem synthetischen Sicherungsdatenträger;
- alle elf Diagnosebereiche erfolgreich, einschließlich Dateiintegrität,
  Paketversionen, HTTPS-Startseite, Datenbank und Dienstrechten.

Das sind Leerlauf-Momentaufnahmen, keine Spitzenwerte oder Cloud-Lastmessungen.
Die 2-GiB-Mindestplanung stützt sich zusätzlich auf die vorherige Laborvalidierung;
dieser neue Installerlauf verwendete ausdrücklich 3 GiB. Für neue Installationen
bleiben 4 GiB im kleinen Labor und 8 GiB für zwei aktive Konten empfohlen.

### Grenzen und Schutz bestehender Systeme

Die vorhandene FCA-Test-VM wurde nicht aufgerufen, neu installiert oder verändert;
es erfolgte kein Zugriff auf Proxmox. Keine echten Cloud-Anmeldungen, keine
Veränderung bestehender Beweisdaten, keine produktiven DNS-/Zertifikatsänderungen
und keine öffentliche Portfreigabe. Schlüssel und CA des Tests waren ausschließlich
kurzlebige synthetische Testmittel.

Die aktuelle Abnahme ersetzt keine vollständige Behörden-Betriebsprobe mit
verschlüsseltem Offsitebackup und der tatsächlichen PKI. Der historische
Laboraufbau wird nicht automatisch in das neue Installationslayout übernommen.
Eine solche Übernahme muss getrennt geplant und gesichert werden. Die Beispiele
`0.6.0-test.1/.2/.3` sind Testversionen, keine produktive Releasefreigabe.
