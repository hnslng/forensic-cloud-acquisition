# Laborbetrieb – Zugang und Administration

## Zugriff

Aktuelles Laborziel: **https://10.0.1.189/**. DHCP ist freigegeben und aktiviert;
bei Adressänderung müssen Ziel, `FCA_PUBLIC_ORIGIN`, nginx und Zertifikat bewusst
angepasst werden. Keine Router-Portweiterleitungen einrichten.

Das HTTPS-Zertifikat wird von der eigenen **FCA Private Lab CA** ausgestellt.
Der öffentliche CA-Nachweis liegt auf der VM in `/etc/fca/tls/lab-ca.crt` und auf
dem Entwicklungsrechner lokal in `.local/fca-lab-ca.crt`. Nur dieses konkrete
Zertifikat nach Fingerprintprüfung am vorgesehenen Laborbrowser als vertrauenswürdig
einrichten. Browser-Zertifikatswarnungen nicht pauschal umgehen; es wurde kein
Vertrauensanker im Betriebssystem des Entwicklungsrechners installiert.

```text
CA SHA-256:
77:6C:AC:1F:A2:37:A4:B8:19:84:ED:BE:C7:A4:62:31:EF:83:98:B0:32:80:85:7F:4F:BF:AB:D0:2A:76:C4:EC
```

Startkonto: `admin`. Das zufällig erzeugte Initialpasswort liegt ausschließlich
als geschützte Secret-Datei unter `/etc/fca/secrets/initial_admin_password`.
Es wird weder im Chat noch in Git dokumentiert. Ein autorisierter Administrator
kann es über den verifizierten SSH-Zugang lokal auslesen. Nach der ersten
Anmeldung über „Passwort ändern“ ein eigenes Passwort setzen (mindestens 14
Zeichen); dabei werden alle Sitzungen widerrufen. Die initiale Passwortdatei
danach kontrolliert entfernen; sie ändert das neue Passwort nicht automatisch.

Der vorbereitete lokale SSH-Zugang verwendet:

```sh
ssh -F .local/fca-ssh-config fca-lab
```

Die Datei und der verifizierte Hostschlüssel bleiben absichtlich außerhalb von
Git. Keine persönlichen privaten SSH-Schlüssel auf die VM kopieren.

Initialpasswort bei Bedarf ausschließlich lokal anzeigen:

```sh
ssh -F .local/fca-ssh-config fca-lab 'sudo cat /etc/fca/secrets/initial_admin_password'
```

## Bedienung

1. Persönlich anmelden und Fall über die Geschäftszahl öffnen oder anlegen.
2. Bearbeiterkürzel je Fallhandlung prüfen; es dient ausschließlich dem Protokoll.
3. Änderungen und Status im eindeutig beschrifteten Fallbereich speichern.
4. Administratoren können unter „Benutzer“ Konten anlegen/deaktivieren und
   im Fall Lese-/Bearbeitungszugriff erteilen oder entziehen.
5. Bei Konfliktmeldung den Fall neu öffnen und den aktuellen Stand prüfen.
6. Abmelden beendet die aktuelle serverseitige Sitzung. Ein bloßes Schließen
   des Browsers ersetzt die Abmeldung nicht; Sitzungen enden nach acht Stunden.

Die Fallübersicht liefert derzeit höchstens 500 zugeordnete Fälle; eine
serverseitige Suche/Paginierung folgt vor größeren Beständen.

## Dienste und Konfiguration

Auf der VM als autorisierter Administrator:

```sh
sudo docker compose --project-directory /opt/fca --env-file /etc/fca/compose.env --profile application ps
sudo systemctl status nginx chrony fca-firewall qemu-guest-agent
sudo python3 /opt/fca/scripts/resource_snapshot.py
```

nginx läuft als Debian-Systemdienst und liefert das getrennte Frontend aus
`/var/www/fca`. API und PostgreSQL laufen in Compose. Die bewusste Abweichung
vom komplett containerisierten Proxy erleichtert private Firewall- und TLS-
Verwaltung auf der kleinen VM. Der API-Port ist nur auf `127.0.0.1:8000`
veröffentlicht. Der Datenbank-Port bleibt unveröffentlicht.

Quellcodeänderungen erfordern einen geprüften Build, DB-Migrationen und den
bewussten Wechsel. Python-Basisimage und PostgreSQL sind auf Digests fixiert;
direkte Anforderungen und vollständig aufgelöste Python-Locks liegen unter
`backend/`. Lock-Updates erfordern erneute Tests. Kein automatisches
`git pull` oder ungeprüftes Online-Skript auf der VM.

## Tests und Wiederherstellung

```sh
sudo bash /opt/fca/scripts/run_phase1_tests.sh
```

Das erzeugt und entfernt ausschließlich `fca_test_phase1`; keine Anwendungstests
gegen echte Arbeitsdaten ausführen. Die einmalige Phase-0-Erstabnahme darf
nicht erneut als Bootstrap über die bestehende Datenbank ausgeführt werden.
`validate_phase0_after_reboot.sh` ist dagegen eine lesende Persistenzprüfung
mit Healthcheck und geeignet für den erhaltenen synthetischen Nachweis.

`/var/backups/fca/phase0.dump` ist die geprüfte **synthetische Restoreprobe**,
kein aktuelles vollständiges Betriebsbackup. Für ein aktuelles Backup sind DB,
Beweisdaten, Konfiguration und benötigte Schlüssel getrennt und konsistent zu
sichern. Vor produktivem Betrieb ist ein unabhängiges verschlüsseltes Ziel
einzurichten und wiederholt praktisch zu restaurieren. Root- und DB-Administratoren
können weiterhin technische Daten verändern; das Audit ist kein WORM-Speicher.
