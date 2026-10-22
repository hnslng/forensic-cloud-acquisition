# Installation – freigegebene Labor-VM

Auf VM 105 erfolgreich ausgeführt. Tatsächliche Versionen, Abnahme und Grenzen
stehen in [Phase 0](phase-0-completion.md), der Anwendungsbetrieb in
[Phase 1](phase-1-status.md) und [Administration](operation.md).

## 1. Unmittelbare Vorprüfung

Rohinventar erneut mit neuem Dateinamen erfassen und `check_vm_plan.py` ausführen.
VM-ID 105, aktuelle RAM-Reserve, Thin-Pool-Auslastung und laufende Gäste prüfen.
Keine automatischen Änderungen an Host, Bridge, bestehenden Gästen oder
Neustarttimern. Bei belegter VM-ID oder fehlenden Reserven den Plan anpassen
und bei wesentlicher Änderung erneut abstimmen.

## 2. Offizielles Image

Debian Stable ist Debian 13 „Trixie“. Das offizielle Verzeichnis ist
https://cloud.debian.org/images/cloud/trixie/latest/ . Am 21.10.2026 meldet
die Generic-Cloud-amd64-Metadatei den offiziellen Build `20261017-2634`.
Vor Import einen datierten Buildpfad, Metadaten und erwarteten SHA-512-Wert
festhalten, damit ein wechselndes `latest` keinen unbemerkten Austausch erlaubt.

Das Verzeichnis bietet `SHA512SUMS`; in der untersuchten Auflistung war keine
separate Prüfsummensignatur vorhanden. Deshalb **keine erfolgreiche
Signaturprüfung behaupten**. Image und Prüfsummen über geprüftes HTTPS von
Debian beziehen und SHA-512 vor Import vergleichen. Das belegt Konsistenz mit
der über HTTPS bezogenen Prüfsumme, keine zusätzliche unabhängige Signatur.
Ergänzend lokalen SHA-256-Wert, URL, Größe und Abrufzeit dokumentieren.
Eine abweichende Prüfsumme stoppt den Import. Beim freigegebenen Lauf wurden
Download und SHA-512-Vergleich erfolgreich ausgeführt; siehe Abschlussbericht.

## 3. Neue VM

Konfiguration gemäß `infrastructure/proxmox/lab-plan.json` anlegen, portable
CPU- und VirtIO-Geräte verwenden, Cloud-Init und QEMU Guest Agent vorsehen.
Nur einen bereits autorisierten öffentlichen SSH-Schlüssel einbringen;
private Schlüssel bleiben auf dem Administratorrechner. Cloud-Init enthält
keine wiederverwendbaren Passwörter. Root- und SSH-Passwortanmeldung abschalten,
bevor der reguläre Betrieb beginnt. Adminzugang mit sudo zuerst in einer
zweiten Verbindung nachweisen. Cloud-Init-Admin-Sudo-Rechte dokumentieren.

DHCP auf `vmbr0`; danach tatsächliche Adresse und Hostschlüsselfingerprint
ermitteln. Fingerprint über die vertrauenswürdige Proxmox-Konsole verifizieren.
Nie unbekannte SSH-Hostschlüssel blind akzeptieren. Autostart nach vorhandenen
Diensten aktivieren. Host und bestehende VMs nicht neu starten.

Die neue Datendisk anhand ihrer eindeutigen Gerätekennung prüfen und nur diese
formatieren. UUID-basiert unter `/srv/fca/evidence` mounten, mit `nodev,nosuid,noexec`.
Fehlender Mount muss Sicherungen verweigern; kein unbemerkter Fallback auf die
Systemdisk. Speichergrenzen vor jedem Auftrag und während langer Downloads
überwachen. Im Labor zunächst nur synthetische Daten.

## 4. Debian-Grundlagen

Systemupdates, OpenSSH, sudo, CA-Zertifikate, curl, Git, Python, Zeitsynchronisierung
und QEMU Guest Agent installieren. Persistentes Journal mit Größenlimit,
Zeitzone Europe/Vienna für Anzeige, UTC für technische Ereignisse.
Firewall: ausschließlich SSH und später HTTPS aus dem privaten Labornetz;
IPv6 gesondert berücksichtigen, keine globalen IPv6-Freigaben.

Docker Engine und Compose-Plugin aus dem offiziellen signierten APT-Repository:
https://docs.docker.com/engine/install/debian/ . Installierte Versionen
protokollieren. Keine Remote-Root-Skripte direkt ausführen. Docker-Firewallpfade
mitprüfen; einfache UFW-Regeln reichen für veröffentlichte Containerports nicht.
Vorerst veröffentlicht Compose überhaupt keinen Port.

## 5. Persistente Infrastruktur

Checkout unter `/opt/fca`, Konfiguration unter `/etc/fca`, Daten unter
`/var/lib/fca`, Testdaten unter `/srv/fca/evidence`. Verzeichnisse und Rechte
explizit setzen. PostgreSQL-Secret lokal zufällig erzeugen, außerhalb von Git,
mit restriktiven Rechten. `.env.example` nach `/etc/fca/compose.env` übertragen
und reale externe Pfade eintragen. Container-Image vor Abnahme auf einen
konkreten Digest festschreiben und tatsächliche Version dokumentieren.

`docker compose config --quiet`, Containerstart mit Healthcheck, erste Migration
und einfache SQL-Abfrage prüfen. Initialisierung des Volumes ändert bestehende
PostgreSQL-Kennwörter nicht nachträglich. Keine Secrets im Compose-Ausdruck
ausgeben. GitHub-Zugriff erfordert keine Kopie persönlicher privater SSH-Schlüssel
auf die VM; zunächst geprüften committed Quellstand administrativ übertragen.

## 6. Pflichtabnahme

1. VM-Status, Debian-Version, DNS und ausgehendes HTTPS nachweisen.
2. SSH-Schlüsselzugriff und abgewiesene Passwortanmeldung prüfen.
3. Zeitabgleich, Firewall, externe Ports und private Quellnetzbegrenzung prüfen.
4. Docker `hello-world`, Compose-Validierung und Datenbank-Healthcheck ausführen.
5. Migration anwenden; Testmarker in DB und synthetische Datei auf Datendisk schreiben.
6. PostgreSQL-Dump außerhalb Checkout erzeugen; Restore in separate leere
   Testdatenbank durchführen, Zeilen und Werte vergleichen; Original erhalten.
7. Nur die neue VM kontrolliert neu starten. SSH, Agent, Zeitabgleich, Docker,
   Datenbank, Testmarker und Datendisk nach Boot erneut prüfen.
8. Bestehende Gäste und Hostressourcen vor/nach dem Test vergleichen.
9. Befehle, Ergebnisse, Versionen, Prüfsummen und verbleibende Einschränkungen
   ohne Geheimnisse im Abschlussbericht festhalten. Erst danach Phase 1 beginnen.

Dieser Ablauf wurde auf der FCA-VM durchgeführt. Die Original-VMs und
Host-Einstellungen blieben unverändert; ausschließlich VM 105 wurde neu gestartet.
