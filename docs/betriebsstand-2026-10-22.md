# Aktueller Betriebsstand – 22. Oktober 2026

Dieser Bericht ergänzt die historischen Phasenberichte. Er beschreibt den tatsächlich
beobachteten Laborstand, keine Freigabe für den Einsatz mit echten Beweismitteln.
Interne Zugänge, konkrete Netzpläne und Wiederherstellungspfade stehen ausschließlich
im geschützten Betreiber-Handbuch und auf den jeweiligen Servern.

## Bereitgestellte Komponenten

- Debian-13-VM: 2 vCPU, 2 GiB RAM; separate System- und Datendisk mit jeweils 32 GiB.
- Dauerhafte DHCP-Zuordnung, privater HTTPS-Name und Zugriff über vorhandenes LAN/WireGuard.
- Nginx, FCA-API, Hintergrundworker und PostgreSQL. Die Anwendung hat keine öffentliche Eingangsfreigabe.
- Öffentlich vertrautes HTTPS-Zertifikat über IONOS DNS-01; Erneuerung einschließlich Deployment-Hook erfolgreich erprobt. Bestehende IP-Adresse leitet auf den HTTPS-Namen weiter.
- Getrennte öffentliche statische Informations-/Datenschutzseiten auf dem vorhandenen IONOS-Webserver. Kein Proxy zur FCA-Anwendung; keine Cloud-Inhalte, Tokens oder Fallinformationen auf diesen Seiten. Eigenes Zertifikat, Erneuerung erprobt; vorhandene Webseiten erhalten.

## Anbieter: ehrlich abgegrenzter Funktionsstatus

| Anbieter/Bereich | Tatsächlicher Stand |
|---|---|
| iCloud Drive/Fotos | Anmeldung und Downloadpfad implementiert; bestehende Läufe vorhanden. Pausierte Läufe werden nicht automatisch gestartet. Vollständigkeit nur für den ausgewählten, tatsächlich untersuchten Umfang. |
| Google Drive | Eigene Web-Anwendung eingerichtet, verschlüsselt in FCA gespeichert. Google-Konsole zeigt „In Produktion“; keine Testnutzerliste mehr erforderlich. Ein vom Betreiber durchgeführter echter Lauf ist in der Datenbank mit 17 abgeschlossenen Dateien, 923.408.392 gespeicherten Bytes und 17 SHA-256-Einträgen bestätigt. Das ist keine vollständige Anbieter-/Behördenabnahme und keine unabhängige Nachprüfung aller gespeicherten Dateien in diesem Dokumentationsschritt. |
| Google Kalender | Implementiert und synthetisch getestet; echter Kalenderlauf nicht abgenommen. |
| Microsoft OneDrive | Adapter, Browser-OAuth und Downloadwarteschlange implementiert und synthetisch getestet. Microsoft-Anbieteranwendung auf der VM noch nicht eingerichtet; kein echter Login oder Microsoft-Download abgenommen. |
| Outlook-Kalender | Adapter mit ausgewähltem Zeitraum implementiert und synthetisch getestet; Echtkonto-Abnahme offen. E-Mails sind nicht implementiert. |

Google „In Produktion“ bedeutet nicht „von Google verifiziert“. Die Konsole weist
weiterhin auf die ausstehende Prüfung und die 100-Nutzer-Grenze bei ungeprüften
Berechtigungen hin. Mandanten- und Kontorichtlinien können Anmeldungen verhindern.
Drive umfasst aktuell „Meine Ablage“; Shared Drives und ausschließlich geteilte
Wurzeln werden nicht eigenständig vollständig inventarisiert. Native Dokumente
sind Exporte. Microsoft umfasst das Standard-OneDrive, nicht sämtliche SharePoint-
Bibliotheken oder weitere Drives. Details: [Anbieterumfang](cloud-acquisition.md).

## Fortschrittskorrektur

Ein echter Google-Lauf enthielt fünf Dateien ohne vorab bekannte Größe. Der alte
Balken blieb deshalb bis zum Abschluss leer. Die korrigierte Oberfläche verwendet:

- Bei bekannter Gesamtgröße den Byte-Anteil.
- Nach vollständiger Erfassung mit unbekannten Größen den Anteil fertig gesicherter Dateien; ausdrücklich als Dateifortschritt gekennzeichnet.
- Bei noch offener Dateierfassung eine Aktivitätsanzeige ohne erfundenen Gesamtprozentsatz.
- Grün/100 Prozent erst bei erfolgreich abgeschlossenem Auftrag. Geschwindigkeit und übertragene Bytes bleiben Messwerte, keine Hochrechnung.

Die vier statischen Oberflächendateien wurden ohne Dienstneustart oder Migration
bereitgestellt und anschließend per HTTPS bytegenau mit dem geprüften Git-Stand
verglichen. Laufende Sicherungen wurden dabei nicht angehalten.

## Tests, Datenerhalt und Nachweise

- Zwölf lokale Node-Tests für Fortschritt und OAuth-Rückkehr erfolgreich.
- [Vollständige CI für 59be95f](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39838766991) erfolgreich: Backend/PostgreSQL, Chromium und gepinnte iCloud-Verträge. Browserprüfung einschließlich 1920 × 1080, 1440 × 900 und 390 × 844.
- [CI der identischen Oberflächendateien in 3efcf36](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39838399930) ebenfalls erfolgreich.
- Vor der Bereitstellung Datenbankdump, Oberflächenarchiv und Vorher-Prüfsummen erstellt. Die beiden zuvor vorhandenen abgeschlossenen/pausierten Läufe, 14 stabile Tabellen und 127 stabile Beweis-/Kontodateien blieben unverändert.
- Ein parallel laufender neuer Sicherungsauftrag aktualisierte bestimmungsgemäß seine eigenen Fortschrittszeilen und Dateien. Diese aktiven Daten wurden nicht als unveränderlicher Bestand bewertet. Kein Rücksetzen oder Überschreiben dieses Laufs.
- Bei der früheren HTTPS-Umstellung wurde ein Backup in eine getrennte Datenbank zurückgespielt; alle 16 Tabellen identisch geprüft. Nachfolgende Konfigurations-/Oberflächenänderungen erhielten eigene Backups; dafür wird kein zusätzlicher vollständiger Restore-Test behauptet.

## Ressourcen: Momentaufnahme nach der Bereitstellung

Rund 1.546 MiB RAM verfügbar bei 1.974 MiB nutzbarem Gesamt-RAM, kein Swap.
Systemdisk rund 5,4 GiB frei (83 Prozent belegt), Datendisk rund 27 GiB frei
(15 Prozent belegt). Dies ist eine Momentaufnahme, kein Lastbenchmark. Vor größeren
Downloads erneut prüfen; parallele Dateien/Konten bleiben standardmäßig auf 4/2 begrenzt.

## Git, Release und Betrieb auseinanderhalten

Die aktuellen Änderungen liegen auf dem gepushten Arbeitszweig
`codex/install-update`; geprüftes Frontend: `59be95f` / identisch zu `3efcf36`.
Ein Push ist kein Merge nach `main` und kein neues signiertes Release. Der zuletzt
benutzte Installations-Release und dessen Signatur werden durch diese Labor-
Bereitstellung nicht stillschweigend ersetzt. API und Worker wurden für die
Fortschrittskorrektur nicht neu gebaut oder gestartet.

Die geschützte Betreiber-Dokumentation enthält die konkreten Hostnamen, DNS-
Einträge, Zertifikats-/Erneuerungspfade, Zuständigkeiten, Sicherungsorte und
Rückfallmaßnahmen. Geheimnisse werden dort nur über ihren Speicherort referenziert;
Passwörter, private Schlüssel und Cloud-Tokens gehören nicht ins Repository.
