# Kompakte Karten, MD5 und gemeinsame iCloud-Sicherung

## Änderungen

Datenmenge und Prüfanzahl erscheinen jeweils einmal. Die Karten wurden vertikal verkleinert; Geschwindigkeit, Restzeit, aktive Downloadplätze und Anbieterkennzeichnung bleiben bestehen. Während laufender Aufträge werden Anmeldung, Bereichsansicht und zusätzlicher Sicherungsstart nicht als deaktivierte Schaltflächen mitgeführt. Pause und Wiederaufnahme bleiben sichtbar, eine laufende Pause erhält einen erklärenden Zwischenstatus.

Migration 0008 ergänzt ausschließlich eine nullable MD5-Spalte. Neue Dateien erhalten MD5 und SHA-256. Historische SHA-256-Werte bleiben erhalten; bei Wiederaufnahme werden fertige Dateien erneut geprüft und fehlende MD5-Werte ergänzt. Bestehende Berichte werden durch die Migration nicht geändert. Ein abweichender vorhandener Hash verhindert die sichere Fortsetzung und muss untersucht werden.

Die iCloud-Auswahl erlaubt Drive, Fotos oder beide zusammen. Gemeinsam erfasste Dateien erhalten nach Kategorie getrennte Quellkennungen und Verzeichnisse; derselbe Pool begrenzt die Übertragungen auf höchstens vier Dateien pro Konto. Die gemeinsame Auswahl umfasst beide sichtbaren Bereiche ohne Ordnerfilter. Ein bereits gestarteter Drive-Lauf erweitert seinen Umfang nicht nachträglich; für Drive und Fotos wird ein neuer Lauf gewählt, sobald der bisherige Lauf beendet ist.

## Pausenursache und Behandlung

Der beobachtete Laborlauf war wegen „Arbeitsspeicher knapp“ automatisch pausiert. Die bisherige Containerprüfung berücksichtigte freigebbaren inaktiven Dateicache als Anwendungsbelegung. Dieser Cache wird nun entsprechend getrennt, echte Speicherknappheit und Containergrenzen bleiben wirksam. Der Koordinator gibt unerwartet beendete Tasks für eine sichere Wiederaufnahme frei, ohne einen laufenden zweiten Verbraucher zu erzeugen. Eine laufende Übertragung darf erst nach Ende des Pausevorgangs fortgesetzt werden.

## Prüfung

Separate PostgreSQL-Testdatenbank; keine produktiven Zugangsdaten oder echten Cloud-Inhalte im Test. Backendprüfungen decken MD5/SHA-256, getrennte Quellkennungen, gemeinsame Bereiche, Pause mit Wiederaufnahme und Speicher-/Cachebewertung ab. Chromium prüft den tatsächlichen Klickablauf Pause → Fortsetzen → Abschluss sowie die gemeinsame iCloud-Auswahl und kompakte Karte bei 1920, 1440 und 390 Pixeln.


## Ergebnis und Bereitstellung

**48 Backendprüfungen und acht Chromium-Workflows erfolgreich** (sechs bestehende und zwei ergänzte Abläufe). Desktop- und Mobilaufnahmen wurden geprüft. Die Bereitstellung auf VM 105 erfolgte mit Schema 8; API und Worker sind gesund, die ausgelieferte Oberfläche wurde über geprüftes HTTPS gegen die Quellen verglichen. Datenbankeinträge und vorhandene Sicherungsdateien wurden vor und nach der additiven Migration geprüft und sind unverändert erhalten. Die Datenbank wurde nicht neu gestartet. Lokale Rückfallsicherung und Nachweise: `/var/backups/fca/compact-md5-20261021/`.

Der vorhandene Lauf mit 49 bereits fertigen Dateien bleibt pausiert. Bei Fortsetzung werden bestehende Dateien geprüft und fehlende MD5-Werte ergänzt; der ursprüngliche Drive-Umfang bleibt erhalten. Die kombinierte Drive-/Fotos-Auswahl wurde synthetisch, noch nicht mit einem vollständigen echten iCloud-Fotobestand abgenommen. Änderungen sind auf GitHub dokumentiert; der aktuelle GitHub-CI-Status war in dieser Sitzung nicht abrufbar.


## Weitere Verdichtung der Karten

Status und gegebenenfalls Pausengrund stehen gemeinsam rechts im Kopf der Karte. Unter dem Balken folgen Datenmenge, Dateierfassung, aktive Downloads, Geschwindigkeit, Restzeit und MD5 in einer umbrechenden Informationszeile. Die eigene Informationszeile oberhalb des Balkens entfällt. Kleinere Innenabstände und ein schmalerer Balken reduzieren die Kartenhöhe; Bedienelemente und Schrift bleiben gut lesbar. Auf Mobilgeräten rückt der Status bei Bedarf unter die Kontobezeichnung, ohne horizontalen Überlauf. Sicherungsverhalten und Datenbank werden durch diese statische Änderung nicht verändert.


Die weitere Verdichtung wurde mit drei Chromium-Workflows geprüft: mehrere Anbieter/Konten, laufende Erfassung mit Downloadanzeige sowie gemeinsamer Drive-/Fotos-Lauf. Desktop bei 1920 und 1440 Pixeln sowie Mobil bei 390 Pixeln ohne horizontalen Überlauf geprüft und visuell kontrolliert. Eine abgeschlossene Desktopkarte benötigt nun ungefähr 200 statt zuvor 260 Pixel Höhe. Die Änderung betrifft ausschließlich statische Frontenddateien.
