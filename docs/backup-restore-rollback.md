# Backup, Wiederherstellung und Rollback

## Backup erstellen

```sh
sudo python3 /opt/fca-current/scripts/fca_admin.py backup
```

API und Worker werden angehalten, PostgreSQL bleibt für den Dump verfügbar.
Neue Anmeldungen und Schreibzugriffe sind währenddessen nicht möglich. Erst
nach Datenbankdump, Wiederherstellungsprobe und konsistenter Archivierung von
Beweisdaten, Cloud-Zustand, Konfiguration und TLS-Dateien werden API/Worker
wieder gestartet. Bei einem Fehler bleiben die Schreiber zur Prüfung gestoppt.
Daher für den Wartungszeitraum sorgen und den freien Backupspeicher vorab prüfen.

Jeder Lauf erhält einen neuen Ordner, ohne Überschreiben:

- `database.dump`: vollständiger PostgreSQL-Custom-Dump.
- `state.tar`: Konfiguration einschließlich Passwörter/Hauptschlüssel,
  verschlüsselter Cloud-Zustand, Beweisdaten und bereitgestellte TLS-Dateien.
- `backup.json`: Hashwerte, Quellrelease und Ergebnis der DB-Restoreprobe.

Ordner 0700, Dateien 0600. Das Archiv enthält entschlüsselungsrelevante
Schlüssel: Backupziel zusätzlich verschlüsseln und unabhängig/offsite sichern.
Schlüsselwiederherstellung organisatorisch getrennt regeln. Keine Archive als
GitHub-Artefakte veröffentlichen. Ein Backup auf derselben Disk schützt nicht
vor deren Ausfall. Releasepaket, Signatur und vertrauenswürdigen Public-Key
separat archivieren. APT-/Docker-Systemkonfiguration und Host-Firewall gehören
zusätzlich zur Serversicherung des Administrators.

## Wiederherstellung auf getrenntem Ziel

**Zuerst immer auf einer isolierten neuen VM restaurieren.** Keine Restorebefehle
über die bestehenden Fälle oder Sicherungsdateien ausführen. Zurückschreiben auf
belegte Datenträger, Löschen einer bestehenden Datenbank oder Ersetzen vorhandener
Schlüssel sind destruktive Maßnahmen und benötigen ausdrückliche Freigabe.

1. Prüfsummen von Dump und Archiv gegen `backup.json` prüfen. Backupquelle und
   Berechtigung prüfen; Hashdatei allein ersetzt kein vertrauenswürdiges Backup.
2. Neue isolierte Debian-VM mit passendem geprüftem FCA-Release und separaten
   leeren Speichermedien vorbereiten. Keine Cloud-Verbindung und keine öffentlich
   erreichbaren Ports. API/Worker vor der Wiederherstellung gestoppt lassen.
3. Archiv zunächst in einen **neuen, leeren, root-geschützten Stagingordner**
   entpacken; keine unkontrollierte Extraktion nach `/`. Struktur/Links prüfen.
   Enthalten sind `config/`, `cloud-auth/`, `evidence/`, `tls/`. UID 10001 und
   Dateirechte erhalten. Volume-ID muss zur restaurierten Datendisk passen.
4. Mit PostgreSQL derselben geprüften Hauptversion eine neue leere Datenbank
   anlegen und `pg_restore --exit-on-error` unter Beibehaltung der Objektbesitzer verwenden. Die FCA-Rollen
   `fca_api` und `fca_migrate` mit den gesicherten Passwortdateien und Rechten
   vor der Wiederherstellung anlegen. Insbesondere müssen die Tabellen anschließend
   weiterhin `fca_migrate` gehören, damit spätere Migrationen möglich bleiben.
   `--no-owner` ohne vollständigen anschließenden Rechte-/Besitzerabgleich ist
   hierfür nicht geeignet. Die Anwendung erst nach diesen Prüfungen freigeben. Keine neue Cloud-Hauptschlüssel-
   Datei erzeugen: vorhandene Tokens benötigen exakt den gesicherten Schlüssel.
5. Auf dem **neuen Ziel** zuerst Konfiguration und Schlüssel aus `config/`, dann
   `cloud-auth/` und `evidence/` übernehmen. Bei abweichender Infrastruktur IP,
   Mountpfad, private HTTPS-Adresse und TLS-Dateipfade kontrolliert anpassen;
   ein Zielkonflikt stoppt die Wiederherstellung. Bestehende OAuth-Registrierungen
   passen nicht automatisch zu einer neuen Adresse. TLS-Material enthält die
   Serverzertifikate, nicht den privaten Schlüssel der internen CA.
6. Vor Workerstart Datenbankschema, Benutzer, Fälle, Konten, Auditanzahl und
   Prüfsummen aller restaurierten Dateien vergleichen. Diagnose ausführen.
   Aufträge bleiben bis zur ausdrücklichen Entscheidung pausiert bzw. Worker
   gestoppt. Insbesondere keinen realen Cloud-Download als Restoretest starten.
7. Erst nach erfolgreicher isolierter Abnahme den regulären Zielwechsel planen.
   Konfliktfreie Adresse/DNS und erneute Anmeldung beim Anbieter separat prüfen.

Der automatisierte Test restauriert den ganzen Dump in eine unabhängige neue
Datenbank und vergleicht synthetische Dateiinhalte sowie Schlüssel im Archiv.
Zusätzlich liest das echte FCA-Backend unter UID 10001 einen restaurierten Fall,
eine restaurierte Datei und den mit dem restaurierten Hauptschlüssel
entschlüsselten synthetischen Cloud-Eintrag aus einer getrennten Verzeichnisstruktur.
Dafür werden die restriktiven Anwendungsrechte ausdrücklich wiederhergestellt:
Cloud-Ordner 0700 und Cloud-Dateien 0600 unter UID 10001. Eine Extraktionsroutine,
die Besitz-/Ordnerrechte absichtlich ignoriert, ersetzt diesen Schritt nicht.
Ein kompletter Behörden-Notfall mit verschlüsseltem Offsiteziel, individueller
PKI und neuen OAuth-Adressen benötigt zusätzlich eine dortige Betriebsprobe.

## Programmrollback

Wenn das Datenbankschema kompatibel geblieben ist, kann auf einen erhaltenen,
nochmals signaturgeprüften lokalen Programmstand gewechselt werden:

```sh
sudo python3 /opt/fca-current/scripts/fca_admin.py rollback \
  --version 0.6.0 --trusted-key /root/fca-release.pub
```

Der Vorgang fragt ausdrücklich nach Bestätigung, erstellt zuerst ein neues
Backup und schaltet nur das Programm um. Fälle, Tokens und Beweisdaten werden
nicht auf einen älteren Stand zurückgeschrieben. Kompatibilität derselben
Schemaversion vor jeder Releasefreigabe praktisch testen.

Ein fehlgeschlagenes Update versucht nur bei unveränderter kompatibler
Schemaversion den vorherigen Programmstand zu starten. Nach Schemaänderungen
bleiben Schreiber angehalten. Kein automatisches SQL-Downgrade und keine
Übernahme älterer Beweisdaten über neuere Sicherungen. In diesem Fall den
geprüften Backupstand zunächst auf separatem Ziel restaurieren und einen
bewussten Wiederherstellungs-/Übernahmeplan freigeben lassen.
