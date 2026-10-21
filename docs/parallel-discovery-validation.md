# Parallele Dateierfassung und Laborbereinigung – 21.10.2026

## Verhalten

Bereits erfasste Dateien werden aus der dauerhaften Warteschlange heruntergeladen, während die weitere Erfassung läuft. Maximal vier gleichzeitige Dateiübertragungen pro Konto und zwei aktive Konten bleiben erhalten. Die Cloud-Karte aktualisiert alle zwei Sekunden die erfassten und geprüften Dateien sowie übertragene Daten und Geschwindigkeit. Solange das Inventar offen ist, erscheint der entsprechende Hinweis; Gesamtprozent und Restzeit werden erst nach vollständiger Erfassung angezeigt. Die Übertragung verarbeitet vorhandene Einträge in Erfassungsreihenfolge, ohne zusätzliche chronologische Sortierung.

Eine vorübergehend leere Warteschlange beendet die Sicherung nicht. Fehler bei der weiteren Erfassung verhindern die Kennzeichnung als abgeschlossen. Wiederaufnahme prüft vorhandene fertige Dateien erneut und übernimmt das gespeicherte Inventar ohne doppelte Einträge. Ein regulärer Dienstneustart reiht laufende Aufträge wieder ein; ausdrücklich angeforderte Pausen bleiben bestehen.

## Prüfungen

- Änderung `c5ac66e`: VM mit echter, getrennter PostgreSQL-Testdatenbank: 42 Backendprüfungen und 6 Chromium-Workflows erfolgreich. Die Anzeige wurde während einer künstlich verzögerten Erfassung mit steigenden Zählerständen und parallel abgeschlossenen Dateien geprüft, einschließlich Mobilansicht. Nach Wegnavigation lief die Sicherung weiter.
- Ergänzung `5e4369d`: drei gezielte VM-Prüfungen erfolgreich: unverändertes Audit nach Entfernung eines Testfalls, Inventarfehler während laufender Downloads samt Wiederaufnahme, geordneter Dienstneustart während der Erfassung.
- GitHub CI für `5e4369d`: **69 Prüfungen erfolgreich**: 11 Infrastruktur-, 43 Backend-, 6 Chromium- und 9 netzisolierte rclone-Vertragstests. [CI-Lauf](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39663087354).
- Synthetische Prüfungen verwenden keine echten Cloud-Zugangsdaten. Eine vollständige Sicherung eines echten iCloud-Kontos ist damit nicht abgenommen.

## Ausdrücklich angeforderte Laborbereinigung

Der Benutzer bestätigte die Entfernung aller bisherigen Fälle, Cloud-Konten und zugehörigen Sicherungsordner. Entfernt wurden **4 Fälle, 2 Cloud-Konten, 1 pausierter Sicherungslauf und 4.466 Dateieinträge**. Übertragen waren 0 Byte. Zusätzlich wurde der alte synthetische Speicher-Testordner entfernt.

Benutzerkonten, Berechtigungen der Benutzer, bestehende Audit-Einträge, Verschlüsselungshauptschlüssel und Anbieter-App-Einstellungen bleiben erhalten. Kontobezogene Anmeldedaten wurden entfernt; für den neuen Versuch ist eine erneute Anmeldung erforderlich. Die Fallzuordnungen zu entfernten Fällen wurden zusammen mit diesen Fällen entfernt.

Migration 0007 bewahrt minimale historische Fallreferenzen getrennt von den aktiven Fällen. Bestehende Audit-Zeilen und ihre Fall-IDs werden dabei nicht verändert. Die API erhält keine Änderungs- oder Löschrechte für Audit-Protokolle oder historische Referenzen. Die administrative Bereinigung ist zusätzlich protokolliert.

Die Bereinigung wurde anhand leerer Datenbanklisten und leerem Fallverzeichnis geprüft. Geschützte Rückfallsicherungen liegen ausschließlich lokal auf der VM unter `/var/backups/fca/user-requested-reset-20261021/`. Sie gehören nicht zur aktiven Fallverwaltung. Datenträger, Einhängepunkt und Volumenkennung bleiben bestehen.
