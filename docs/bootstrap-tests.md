# Abnahme des Bootstrap-Installers – 22.10.2026

Der signierte Installationskandidat **0.6.0-rc.1** wurde veröffentlicht und über seinen echten öffentlichen GitHub-Installationsbefehl auf einer weiteren frischen Debian-13-VM installiert. Auf dem Zielserver waren weder GitHub-Anmeldung noch persönlicher Token erforderlich. Die Sichtbarkeit des Repositories wurde durch den Agenten nicht verändert.

## Ergebnisse

- **149 automatisierte Einzeltests bestanden:** 43 für Installer/Bootstrap und 106 für Infrastruktur, Abhängigkeiten, Backend, Browser und iCloud ohne Echtkonto.
- **Frische Offline-VM:** Installation ohne Internetroute, mit leerem separatem Testdatenträger; Wiederaufnahme nach absichtlichem Paketmanagerfehler; Wiederholung; Update und fehlgeschlagenes Update; Backup, separate Wiederherstellung, Rollback und Neustart bestanden.
- **Frische Bootstrap-VM:** unveränderter Ein-Befehl-Start über kontrolliertes HTTPS, Signatur-/Prüfsummenprüfung, interaktive Antworten über echte Konsole, neue Labor-CA, explizit bestätigter leerer Laborordner; zusätzlicher unformatierter Testdatenträger blieb unverändert. Wiederaufnahme, HTTPS-Anmeldung, Datenerhalt, Updates, Restore und Neustart bestanden.
- **Frische VM mit veröffentlichtem Release:** exakter Befehl aus `releases/v0.6.0-rc.1/INSTALL.txt`, tatsächlicher anonymer GitHub-Download, vollständige Installation, sichere Anmeldung/Abmeldung, synthetische Fälle/Rechte/Cloud-Konten, Backup mit Restoreprobe, Wiederherstellung verschlüsselter synthetischer Kontodaten und Neustart bestanden.
- Archiv nach lokalem Signieren durch CI **byteidentisch** rekonstruiert und veröffentlicht; CI benötigt dafür keinen privaten Signierschlüssel.
- Manipulation, falsche Signatur, unsichere Archivpfade, Links/Spezialdateien, doppelte Dateien, falscher Speicher und anonyme Nichtverfügbarkeit werden abgewiesen.

Die Datenvergleiche erfassen sämtliche vorhandenen FCA-Tabellen plus synthetischen Kontrollwert, verschlüsselte Cloud-Dateien, Schlüssel und Sicherungsdaten. Die Wiederherstellungsprobe liest Fall, Beweisdatei und verschlüsselten Kontozustand mit dem tatsächlichen Backend unter dessen Dienstbenutzer aus einer getrennten Wiederherstellungsumgebung.

## Nachweise

- [Offline- und Bootstrap-VMs](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39726255140)
- [Erneute Offline-/Bootstrap-Abnahme des Veröffentlichungsstands](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39727511133)
- [Anwendungstests](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39727511046)
- [Signierte Veröffentlichung und tatsächliche öffentliche GitHub-Installation](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39727506182)
- [Maschinenlesbarer Prüfbericht mit Prüfsummen](test-results/bootstrap-validation.json)

Geprüfter Paketquellstand: `33db5a456ad3076f6b80f852dbd702a8020cbdb0`. Der Veröffentlichungsablauf wurde mit `85cba4e` ausgeführt. Das Release enthält genau den geprüften Nutzdatenstand; Signatur und Versionsmanifest wurden anschließend lokal mit dem dauerhaften Releaseschlüssel erzeugt. Dieser private Schlüssel ist nicht Teil des Repositories, der CI-Artefakte oder der Installation.

## Grenzen und Betriebsangaben

Die isolierten VMs hatten **2 vCPU, 3 GiB RAM und 32 GiB Systemdisk**; der Offlinefall zusätzlich 8 GiB Testdatenträger. Dies ist eine Installations-/Wiederherstellungsabnahme, kein Lasttest großer Cloud-Sicherungen und kein Nachweis für Spitzenverbrauch. Für das Labor sind 4 GiB RAM empfehlenswert; für den Behördenbetrieb einen eigenen ausreichend großen Sicherungsdatenträger und getrennte Backups verwenden. Die bisherige Mindestkonfiguration und Hinweise stehen in der [Installationsanleitung](installation.md).

Es gab keine echten Cloud-Anmeldungen, keinen Proxmox-Zugriff und keine Neuinstallation oder Veränderung der vorhandenen FCA-Test-VM. Im Labor muss der Administrator das neu erzeugte öffentliche CA-Zertifikat am Arbeitsplatz vertrauen. Für Behördennetze bleiben bestehender WireGuard-Zugang, interne Namensauflösung und Zertifikate administrative Voraussetzungen.

Der langlebige private Signierschlüssel liegt ausschließlich im geschützten lokalen Release-Verzeichnis `.local/release-signing/` außerhalb der Versionierung. Separat geschützt sichern; künftige Updates benötigen denselben freigegebenen Schlüssel. Endserver erhalten nur den öffentlichen Prüfschlüssel.

## Kurzer Startaufruf – Installer v1

Der kurze Befehl steht am Anfang der README und in `releases/START-v1.txt`. Er umfasst 332 Zeichen, einschließlich fester Version, direktem Download, separat vorgegebenem SHA-256-Wert und Start. Ein einziges Kopieren des gesamten Blocks genügt.

**Abnahme erfolgreich:** [GitHub-Testlauf 39731103469](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39731103469), Stand `cd15cbe`. Acht zusätzliche Sicherheitstests bestehen. Der exakte README-Aufruf wurde in einer neuen Debian-13-VM mit 2 vCPU, 3 GiB RAM und 32 GiB Systemdisk ausgeführt. Wget war zuvor in dieser wegwerfbaren Testumgebung entfernt worden, um die automatische Nachinstallation zu prüfen. Es waren keine FCA-Dienste vorinstalliert und keine GitHub-Tokens im Gast vorhanden.

Der tatsächliche öffentliche Download vom Tag `installer-v1`, die feste Starter-Prüfsumme, der bisherige Bootstrap, vollständige Einrichtung, HTTPS-Anmeldung/Abmeldung, synthetische Daten, Backup/Restore einschließlich verschlüsseltem Kontozustand und Gast-Neustart wurden geprüft. Der zusätzliche unformatierte Testdatenträger blieb unformatiert. Die bestehende FCA-Test-VM wurde dabei nicht verwendet oder verändert. Der Testtreiber beantwortet gezielt die FCA-Eingabeaufforderungen; Paketmanager-Ausgaben werden nicht als Formularfragen interpretiert.

Die Starter-Prüfsumme wurde lokal aus dem überprüften Quellstand berechnet und nach einem weiteren anonymen GitHub-Download erneut unabhängig abgeglichen. Prüfsummen-/Signaturprüfungen des bereits veröffentlichten Releases bleiben unverändert. Der alte ausführliche Bootstrap-Aufruf und der Offlineweg bleiben gültig. [Maschinenlesbarer Nachweis](test-results/short-install-validation.json).
