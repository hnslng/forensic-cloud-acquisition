FCA 0.6.0-rc.1 – Installationskandidat für Debian 13 amd64

Enthält die bestehende FCA-Anwendung mit interaktiver Installation, signiertem Online-Bootstrap und unverändertem Offlineinstaller.

Installation: den vollständigen Befehl aus INSTALL.txt als root auf einer neuen Debian-13-VM ausführen. Keine GitHub-Anmeldung am Server notwendig. Kein Formatieren von Datenträgern.

Im Labor kann eine private CA erzeugt werden; deren öffentliches Zertifikat anschließend am Arbeitsplatz vertrauen. Behördenbetrieb benötigt vorbereiteten WireGuard-Zugang, internen HTTPS-Namen, interne CA und eigenen Sicherungsdatenträger.

Frische VM-Tests (Online-Bootstrap und Offlineinstallation, Wiederaufnahme nach Installationsfehler, Anmeldung, Daten-/Schlüsselerhalt, Update, Backup/Restore, Rollback, Neustart): https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39726255140

Getesteter Quellstand: 33db5a456ad3076f6b80f852dbd702a8020cbdb0

Das signierte Manifest enthält vollständige Datei- und Paketprüfsummen sowie Container-Inhalts-IDs. Updates sind separat auszuführen. Bestehende FCA-Laborinstallation nicht mit diesem Installer neu installieren.

Dies ist ein Releasekandidat für Installationstests, keine rechtliche oder behördliche Produktzertifizierung.
