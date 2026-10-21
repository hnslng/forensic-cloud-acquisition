# Prüf- und Bereitstellungsnachweis 0.5.0

Stand: 21.10.2026, VM 105. Code: `5516154114ab1eee89371fa5bc6473c2506040ab`.

## Ergebnis

Die Laborversion ist unter der unveränderten privaten HTTPS-Adresse bereitgestellt. API und neuer Sicherungsdienst sind gesund. Die freigegebene dunkelblaue Gestaltung, breite Karten und der TRIAGE//BOX-Fallablauf bleiben erhalten. Es wurden keine echten Anbieterzugangsdaten verwendet und keine tatsächliche Cloud-Kontosicherung als abgenommen erklärt.

[Erfolgreicher GitHub-CI-Lauf des bereitgestellten Codes](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39657986871).

## Automatisierte Prüfungen

| Bereich | Erfolgreich | Inhalt |
| --- | ---: | --- |
| Infrastruktur | 11 | Ressourcenplanung, Schutz vor fremden VM-/Hoständerungen, sichere Inventarabfragen |
| PostgreSQL/API/Downloadverwaltung | 40 | Ursprüngliche Rechte/Benutzer/Audit, sichere Fallordner, Mehrfachkonten, dauerhafte Aufträge, Parallelität, Prozessabbruch/Neustart, Netzabbruch, Integrität, Speicherknappheit, OAuth/PKCE, Anbieter-Verträge |
| Chromium | 6 | Fallanlage/-start, mehrere Konten, Einstellungen/Rechte, iCloud-2FA mit synthetischen Antworten, Hintergrundsicherung und Wiederöffnen, integrierte Fortschritte/Berichte, direkter Rückweg nach OAuth |
| Gepinnter rclone ohne Netzwerk | 9 | Verschlüsselung, falscher Schlüssel/Restore, Kontotrennung, private Unix-Steuerung, echte parallele Dateikopien und Inventarisierung |
| **Gesamt** | **66** | Kein Ersatz für die Echtkonto-Abnahme |

Die vollständigen PostgreSQL-/API- und Browserprüfungen wurden auf der Test-VM mit getrennter, nachher gelöschter Testdatenbank durchgeführt. Zusätzlich wurden die inklusive Outlook-Enddatumsgrenze sowie lange Unicode-Fallnummern/-Dateinamen auf der tatsächlichen VM-Laufzeit geprüft. Der endgültige Code einschließlich dieser Korrekturen besteht sämtliche Prüfungen nochmals in GitHub CI.

Der Prozessneustarttest beendet einen echten Worker-Prozess, startet einen neuen und prüft die gespeicherte Warteschlange mit drei Konten: höchstens zwei aktive Konten, Wiederaufnahme unterbrochener Aufträge, keine doppelten Dateieinträge. Einzeldateien werden in höchstens vier parallelen Übertragungen je Konto verarbeitet. Ein echter lokaler TCP-Server bricht eine Dateiübertragung vorzeitig ab; der Wiederholungsversuch erzeugt exakt die erwarteten Bytes ohne Verdoppelung.

Google-Workspace-Exporte, Outlook-Serien/Ausnahmen im definierten Zeitraum, Microsoft-Downloadweiterleitungen ohne Weitergabe des Bearer-Tokens und explizites Auslassen verknüpfter/Paket-Ordner sind separat geprüft. Exportgrößen, die der Anbieter nicht nennt, werden nicht als bekannte Gesamtdatenmenge behandelt.

## Desktop und Mobil

Geprüft: 1920 × 1080, 1440 × 900 und 390 × 844. Eine volle Cloud-Karte pro Zeile, keine horizontalen Überläufe, nutzbare Modale und sichtbarer integrierter Fortschritt.

Die folgenden Aufnahmen zeigen **ausschließlich synthetische Testdateien und simulierte Anbieterantworten**, keine erfolgreiche Apple-Kontosicherung:

- [Desktop 1920 × 1080](images/cloud-acquisition-1920-synthetic.png)
- [Desktop 1440 × 900](images/cloud-acquisition-1440-synthetic.png)
- [Mobilansicht](images/cloud-acquisition-mobile-synthetic.png)

## Datenerhalt und Wiederherstellung

Geschützte Nachweise verbleiben auf der VM unter `/var/backups/fca/phase3-cloud-acquisition/`; Datenbankarchive, Anmeldedaten und Schlüssel werden nicht nach GitHub übertragen.

- Vollständiges Vorher-Backup der Datenbank (Schema 5), bisheriger Quellen/Oberfläche, Sicherungsdateien, verschlüsselter Anbieterzustände und des zugehörigen externen Hauptschlüssels.
- Tatsächliche Wiederherstellung der alten Datenbank in eine separate Datenbank; sämtliche Tabellenzeilen identisch.
- Tatsächliche Wiederherstellung des Dateiarchivs in ein isoliertes Verzeichnis; alle Datei-SHA-256 einschließlich des Schlüssels identisch.
- Migration 6 ergänzt ausschließlich Warteschlange, Einstellungen und Verzeichniszuordnungen. Bestehende Tabellenzeilen wurden anhand ihrer Fingerprints geprüft und unverändert erhalten: Audit, Fallmitglieder, Fälle, Cloud-Katalog, Cloud-Anmeldebegrenzung, FCA-Anmeldebegrenzung, Phase-0-Probe, Sitzungen und Benutzer.
- Anschließendes vollständiges Backup und Wiederherstellung **auch der neuen Schema-Version 6**. Alle alten und neuen Tabellenzeilen identisch.
- Sämtliche bisherigen Dateiinhalte und der Hauptschlüssel nach der Bereitstellung nochmals identisch.
- VM-Boot-ID und PostgreSQL-Container-ID/Startzeit vor/nach Bereitstellung identisch. Kein VM-/Host-Neustart, keine Neuerstellung des Datenbankcontainers, keine öffentlichen Portfreigaben.

Für künftige produktnahe Backups müssen Datenbank, Sicherungsdateien und verschlüsselte Anbieterzustände samt Schlüssel als zusammengehöriger Stand gesichert werden. Aktive Sicherungsarbeiten vorher anhalten bzw. API/Worker geordnet stoppen, damit Dateisystem und Warteschlange konsistent sind. Wiederherstellungen zuerst getrennt prüfen. Ein fehlender Hauptschlüssel wird nicht automatisch ersetzt.

## Laufzeitprüfung

- HTTPS mit der konkreten privaten Labor-CA erfolgreich verifiziert, keine pauschal deaktivierte Zertifikatsprüfung.
- Alle vier ausgelieferten Frontend-Dateien stimmen bytegenau mit dem bereitgestellten Code überein.
- API-Gesundheit und Worker-Leader-/Datenbankprüfung erfolgreich.
- Anonyme Zugriffe auf Fälle, Anbieterstatus und Sicherungseinstellungen abgewiesen.
- OAuth-Rückkehrseite unter der bestehenden CSP erreichbar; Callback-Code wird über eigene lokale Skriptdatei verarbeitet.
- Keine LAN-Freigabe für HTTP, PostgreSQL oder den internen API-Port. Worker hat keinen veröffentlichten Port.

## Ressourcen

Momentaufnahme unmittelbar nach Bereitstellung am **21.10.2026, 21:06 Uhr (Wien)**, ohne Cloud-Sicherungsauftrag:

| Messwert | Beobachtung |
| --- | ---: |
| Verfügbarer RAM | 1,32 GiB |
| API-Speicher | ca. 49,8 MiB, Grenze 384 MiB |
| Worker-Speicher | ca. 30,3 MiB, Grenze 512 MiB |
| PostgreSQL-Speicher | ca. 55,0 MiB, Grenze 512 MiB |
| Freier Systemspeicher | 11,77 GiB |
| Freier Sicherungsdatenträger | 30,61 GiB |
| Standardreserve auf Sicherungsdatenträger | 2 GiB |
| Rechnerisch für zusätzliche Sicherungsdaten verfügbar | ca. 28,61 GiB |

Die Systemdisk enthält auch Prüfimages, Build-Caches und die geschützten Wiederherstellungskopien. Diese Momentaufnahme und die kleinen synthetischen Übertragungen sind kein Nachweis des Speicher-/CPU-Bedarfs großer echter Cloudbestände. Die vorhandene Testdatendisk reicht nicht für eine vollständige Cloud mit mehr als dem verfügbaren Umfang; vor größeren Aufträgen erneut prüfen und gegebenenfalls Speicher bereitstellen. Die Anwendung überwacht die konfigurierte Reserve und pausiert bei Knappheit.

## Ehrlicher Anbieterstatus

iCloud Drive/Fotos sind technisch für Anmeldung, Ansicht und Sicherungsstart vorbereitet. Google Drive/Kalender und Microsoft OneDrive/Outlook-Kalender sind implementiert, benötigen jedoch registrierte Anbieteranwendungen; Google zusätzlich eine zugelassene HTTPS-Domain statt der privaten Labor-IP. **Alle tatsächlichen Anbieter-Testkonto-Abnahmen bleiben offen.** Keine simulierten Werte oder synthetischen Testkonten wurden in die produktive Labordatenbank übernommen.

Bedienung: [Kurzanleitung](kurzanleitung.md). Genaue Bereichsdefinitionen und nicht unterstützte Inhalte: [Funktionsstatus und Grenzen](cloud-acquisition.md).
