# FCA – Kurzanleitung

## Einen Fall sichern

1. **Fall anlegen** wählen. **Fallnummer**, **Fallbezeichnung** und **Bearbeiter** eintragen, dann **Fall starten**.
2. **+ Cloud hinzufügen** wählen. Anbieter und eine freie Bezeichnung eingeben, beispielsweise „iCloud – Testkonto“. Weitere Konten können im selben Fall ergänzt werden.
3. Auf der Cloud-Karte **Anmelden** wählen. Bei iCloud Apple-ID, reguläres Passwort und gegebenenfalls den Apple-Bestätigungscode eingeben. Google und Microsoft öffnen ihre eigenen Anmeldeseiten und führen danach direkt in den Fall zurück.
4. **Sicherung starten** wählen. Datenbereich und angezeigten Umfang prüfen. Bei iCloud stehen **Drive und Fotos**, **Nur iCloud Drive** und **Nur iCloud Fotos** zur Wahl. Gemeinsam werden beide sichtbaren Bereiche in getrennten Unterordnern gesichert; ein Ordnerfilter ist dabei nicht vorgesehen. Für den ersten iCloud-Test einen kleinen vorbereiteten Ordner auswählen bzw. dessen relativen Pfad eintragen. Bei Outlook den Kalenderzeitraum festlegen.
5. Mit **Sicherung starten** bestätigen. Danach darf der Browser geschlossen werden. Die Übertragung läuft auf der FCA-VM weiter.

## Fortschritt und Berichte

- Die Anzahl **Dateien erfasst** steigt während der Suche laufend. Bereits erfasste Dateien werden parallel heruntergeladen. **Dateierfassung läuft noch** bedeutet, dass der Gesamtumfang noch offen ist. Erst nach Ende der Erfassung erscheinen Gesamtfortschritt und gegebenenfalls Restzeit.
- **x von 4 Downloads aktiv** zeigt belegte Übertragungsplätze. Freie Plätze werden laufend nachbesetzt. Die **Gesamtgeschwindigkeit** umfasst die laufenden Dateien; bei Anbieterdrosselung erscheint ein Hinweis.
- Die kompakte Cloud-Karte zeigt Datenmenge und geprüfte Dateianzahl jeweils einmal; sichtbar ist MD5. SHA-256 bleibt zusätzlich im Prüfprotokoll. Historische Dateien erhalten MD5 erst bei erneuter Prüfung. Eine Restzeit erscheint nur bei bekanntem Gesamtumfang.
- **Pausieren** hält eine Sicherung an. Nach Ende der laufenden Verarbeitung wird **Fortsetzen** angeboten. Nach einem Dienst-/VM-Neustart werden zuvor laufende Aufträge automatisch wieder aufgenommen.
- Bereits fertig geprüfte Dateien bleiben erhalten. Unfertige Einzeldateien werden erneut vollständig übertragen.
- **Sicherungsläufe** öffnet frühere Läufe mit **Sicherungsbericht** und **Dateien und Prüfsummen**.
- **Abgeschlossen** gilt ausschließlich für den angezeigten, erfolgreich inventarisierten Umfang. Fehlende oder nicht übertragbare Inhalte führen zu **Unvollständig** oder **Fehlgeschlagen**.

## Wo liegen die Dateien?

Auf dem konfigurierten Sicherungsdatenträger, im Labor unter `/srv/fca/evidence/FCA-Sicherungen/`. Jeder Fall, jedes Konto und jeder Lauf hat ein getrenntes Verzeichnis. Die Fallnummer erhält zur eindeutigen Zuordnung eine Fall-ID. Innerhalb des Laufordners liegen die übertragenen Dateien unter **Daten**, die Dokumentation unter **_FCA**. Frühere Läufe werden nicht überschrieben.

## Einstellungen

Unter **Einstellungen → Technischer Status** kann ein Administrator die Parallelität reduzieren. Auf der Test-VM gelten maximal **4 Dateien pro Konto** und **2 gleichzeitig aktive Konten**; 2 GiB bleiben als Speicherreserve frei.

Google und Microsoft benötigen einmalig eine registrierte Anbieteranwendung. Die Einrichtung und die tatsächlich unterstützten Datenbereiche sind im [Anbieter- und Funktionsstatus](cloud-acquisition.md) beschrieben. Die Google-Webanmeldung benötigt außerdem eine zugelassene HTTPS-Domain; die private Labor-IP allein genügt dafür nicht.

Die synthetischen Prüfungen ersetzen keine vollständige Abnahme der einzelnen Datenbereiche mit einem vorbereiteten Anbieter-Testkonto. Die iCloud-Anmeldung wurde im Labor bereits erfolgreich durchgeführt; eine vollständige Sicherung bleibt zu prüfen.
