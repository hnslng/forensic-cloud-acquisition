# FCA mit einem Befehl installieren

## Voraussetzung und Veröffentlichungsstand

Debian 13 **amd64**, root-Konsole mit Internetzugang, vorhandene private IP, mindestens 2 vCPU / 2 GiB RAM (4 GiB empfohlen), mindestens 32 GiB Systemdisk. Für größere Sicherungen einen eigenen Datenträger und getrennten Backup-Speicher vorsehen. DNS, WireGuard und die interne CA werden im Behördennetz vorab administriert; FCA richtet keine öffentlichen Ports ein.

**Solange Repository und Release privat sind, ist eine anonyme GitHub-Installation technisch nicht möglich.** FCA fordert keinen GitHub-Login oder persönlichen Token an. Die Umstellung des bestehenden Repositories `hnslng/forensic-cloud-acquisition` auf öffentlich nimmt ausschließlich der Eigentümer vor. Vor einer Veröffentlichung müssen auch Historie und alte Dateien auf interne Informationen geprüft werden. Der Installer ändert die Sichtbarkeit nicht.

Ein Produktionsrelease und dessen dauerhafter Signierschlüssel sind unabhängig von den synthetischen CI-Testschlüsseln freizugeben. `0.6.0-test.1` ist ausschließlich ein Testpaket und kein freigegebenes Behördenrelease.

## Verfügbarer Installationskandidat

[**v0.6.0-rc.1**](https://github.com/hnslng/forensic-cloud-acquisition/releases/tag/v0.6.0-rc.1) ist als signierter Releasekandidat veröffentlicht. Den exakten, an diese Version gebundenen Befehl enthält [INSTALL.txt](../releases/v0.6.0-rc.1/INSTALL.txt). Auch der Download aus dem Release funktioniert ohne Anmeldung. Archiv und Startprogramm sind fest vorgegeben; der Offlineinstaller steckt im selben Paket.

Der dauerhafte Ed25519-Signierschlüssel bleibt auf dem geschützten Release-System. Er wird nicht in GitHub oder CI gespeichert. **Diesen privaten Schlüssel separat geschützt sichern**, damit zukünftige Updates mit demselben freigegebenen Schlüssel signiert werden können. Der öffentliche Schlüssel und alle Signaturen sind unter `releases/v0.6.0-rc.1/` nachvollziehbar.

## Bevorzugter kurzer Installationsaufruf

Der kurze Aufruf steht gut sichtbar am Anfang der [README](../README.md#installation-auf-einer-neuen-debian-13-vm) und separat in [START-v1.txt](../releases/START-v1.txt). Den gesamten mehrzeiligen Befehl als root kopieren. Er installiert bei Bedarf die festgelegten Debian-Downloadwerkzeuge, lädt `start.sh` vom festen Tag `installer-v1`, prüft die **im Aufruf vorgegebene** SHA-256 und startet das verifizierte Skript. Ein privates temporäres Verzeichnis schützt die heruntergeladene Datei vor fremden Schreibzugriffen.

Das Startskript prüft Debian/Architektur, ergänzt fehlende Bootstrap-Abhängigkeiten aus signierten Debian-Quellen, prüft den festgelegten Bootstrap gegen dessen bisherigen SHA-256 und startet ihn mit unveränderter interaktiver Konsole. Danach folgen die bestehenden Ed25519-, Archiv-, Manifest- und Dateiprüfungen. Das veröffentlichte Release und der Offlineinstaller werden nicht ersetzt oder abgeschwächt.

Die Starter-Prüfsumme wurde aus dem geprüften lokalen Quellstand berechnet und zusätzlich nach dem anonymen GitHub-Download abgeglichen. Der Wert im Aufruf muss über einen unabhängig freigegebenen Kanal bezogen werden, etwa den separat übermittelten Abschlussbericht oder eine administrativ geprüfte Anleitung. Wer den gesamten Befehl samt Prüfwert austauschen kann, könnte auch diesen Schutz austauschen. Daher keine gleichzeitig heruntergeladene `.sha256`-Datei als alleinigen Vertrauensanker verwenden.

## Bisheriger vollständiger Bootstrap-Aufruf

Jedes freigegebene Release erhält eine **eigene `INSTALL.txt` mit genau einem kopierbaren Befehl**. Dieser wird aus dem endgültig signierten Archiv erzeugt. Er enthält die feste Releaseadresse und den SHA-256-Wert des zugehörigen Bootstrap-Programms. Deshalb gibt es bewusst keinen beweglichen `latest`-Befehl und keinen vorab erfundenen Produktions-Prüfwert.

Als root den vollständigen Befehl aus dieser Datei direkt in der Serverkonsole ausführen. Kein `curl | bash`. Kein Klonen des Git-Repositories und kein Docker-Hub-Konto notwendig. Fehlen Python 3 mit Standardbibliothek, OpenSSL oder die öffentlichen CA-Zertifikate, installiert der Befehl die festgelegten direkten Debian-Paketversionen aus den signierten Debian-Quellen. Die zugehörigen Debian-Abhängigkeiten löst APT über seine geprüften Paketmetadaten auf. FCA selbst, Docker, Compose, PostgreSQL, nginx und sämtliche Betriebssystempakete des FCA-Pakets kommen anschließend aus dem signierten, versionierten Offlinepaket; Container werden über ihre Inhalts-ID geladen und nicht beim Serverstart neu gebaut.

Die vollständigen Paketversionen stehen im signierten Release-Manifest. Ist eine benötigte Bootstrap-Paketversion nicht mehr verfügbar, wird angehalten. Es gibt keinen Rückfall auf einen ungeprüften aktuellen Stand.

## Geführte Einrichtung

Abgefragt werden Betriebsart, private Serveradresse, HTTPS-Name, zugelassene Netze, Sicherungs- und Backup-Speicher sowie Ressourcenprofil. Eindeutig erkennbare Werte sind vorbelegt. Im Behördenbetrieb werden zusätzlich die vorhandene Zertifikatskette, der Schlüssel und die CA-Datei angegeben.

Im privaten Labor kann FCA eine neue private CA und ein Serverzertifikat erzeugen. Das **öffentliche** CA-Zertifikat `/etc/fca/tls/ca.pem` muss anschließend am Ermittler-PC als vertrauenswürdig hinterlegt werden. Schlüssel und Zugangsdaten niemals auf Arbeitsplatzrechner oder in GitHub kopieren. Ein eigener HTTPS-Name muss im internen DNS auf diese VM zeigen. Die Anwendung benötigt keinen festen Domainnamen im Code.

Am Sicherungspfad muss normalerweise ein leerer Datenträger eingebunden sein. **Der Installer partitioniert und formatiert niemals.** Für eine frische Labor-VM ist alternativ ein neuer leerer Ordner auf dem vorhandenen Dateisystem möglich. Dazu ist ausdrücklich `SYSTEMSPEICHER` einzugeben. Dadurch teilen Sicherungen und Betriebssystem die Kapazität; die Speicherüberwachung bleibt aktiv. Der Installer bindet diese Auswahl an die Dateisystem-UUID und eine FCA-Kennung. Ein fehlender Datenträger führt weiterhin zum Startabbruch. Für den Behördenbetrieb ist diese Ordneralternative gesperrt.

Bestehende Dateien am gewählten Sicherungspfad, bestehende TLS-Dateien und vorhandene unverwaltete FCA-Installationen werden nicht übernommen oder überschrieben. Keine anderen Proxmox-Gäste werden angesprochen. Die vorhandene FCA-Test-VM wird nicht neu installiert.

Nach erfolgreicher Diagnose zeigt FCA die **fertige HTTPS-Webadresse**, den Benutzernamen `admin` und den geschützten lokalen Ablageort des einmaligen Startpassworts. Passwort beim ersten Anmelden ändern. Google-/Microsoft-App-Konfigurationen werden später in den Einstellungen hinterlegt, nicht bei jeder Installation oder Kontoanmeldung.

## Prüfung vor Ausführung

1. Der kopierte Startbefehl prüft die Bytes des Bootstrap-Programms gegen seinen fest vorgegebenen SHA-256-Wert.
2. Der Bootstrap akzeptiert ausschließlich sein festgelegtes Release aus `hnslng/forensic-cloud-acquisition` und HTTPS-Weiterleitungen an die GitHub-Downloadhosts.
3. Die kleine Archiv-Prüfsummendatei wird mit dem eingebauten Ed25519-Vertrauensschlüssel geprüft.
4. Archivgröße und SHA-256 müssen exakt der freigegebenen Version entsprechen.
5. Vor dem Entpacken werden Dateipfade, Links, Spezialdateien, doppelte Einträge und die Gesamtgröße geprüft. Es gibt kein unbeschränktes Entpacken mit `extractall`.
6. Die innere Manifest-Signatur und Version werden geprüft. Erst danach läuft heruntergeladener Installationscode, der nochmals alle Paketdateien prüft.

Ein kompromittierter Kanal, über den der Benutzer **den kompletten Befehl einschließlich Prüfwert** erhält, ist dadurch nicht abgesichert. Den Installationsbefehl über einen freigegebenen, vertrauenswürdigen Kanal verteilen. Signierschlüssel und freigegebene Prüfschlüssel bleiben Administrationsaufgaben.

Bei Verbindungsfehlern wird der Download begrenzt wiederholt. Eine erneut gestartete Installation erhält bereits angelegte Passwörter und Schlüssel. Eine fertig eingerichtete gleiche Version wird lediglich geprüft. Eine andere Version benötigt `update.sh`; der Bootstrap führt kein verstecktes Update aus.

## Offlineinstallation, Updates und Wiederherstellung

Der bestehende [Offlineinstaller](installation.md) bleibt unterstützt. Das Archiv ist dasselbe; lediglich die Beschaffung entfällt. Die geführte Einrichtung kann aus einem zuvor unabhängig geprüften Paket mit `python3 scripts/fca_guided_install.py --package /absoluter/paketpfad --trusted-key /separater/release.pub` aufgerufen werden.

Updates sind weiterhin getrennt und erhalten Fälle, Konten, Datenbanken, verschlüsselte Cloud-Tokens und Sicherungen. Vorgehen: [Backup, Wiederherstellung und Rollback](backup-restore-rollback.md).

## Release erstellen (einmalig je Version, nicht auf Ermittler-PCs)

Nach grünen Anwendungstests und frischen VM-Tests das bereits signierte Offlinearchiv zusätzlich verarbeiten:

```sh
python3 scripts/build_bootstrap.py \
  --version 0.6.0 \
  --archive /release/fca-0.6.0.tar.gz \
  --trusted-key /sicher/fca-release.pub \
  --output /release/bootstrap
```

`0.6.0` ist hier ein Beispiel, kein bereits veröffentlichtes Release. Archiv, `.sha256`, `.sha256.sig`, `fca-bootstrap.py`, `INSTALL.txt` und `bootstrap-lock.json` gehören als Assets in dasselbe Release mit Tag `v0.6.0` des bestehenden Repositories. Keine persönliche GitHub-Anmeldung wird auf den Zielserver übertragen. Der langfristige private Signierschlüssel bleibt ausschließlich auf dem geschützten Release-System; denselben freigegebenen Schlüssel auch für Updates verwenden.

Der Offlinepaketbau und die äußere Signaturprüfung sind in [Releasepakete](release-packages.md) beschrieben. Signierte Versionen nach Veröffentlichung niemals unter demselben Namen ersetzen. Bei Änderungen eine neue Version erstellen und erneut testen.

## Veröffentlichung ohne Signierschlüssel in GitHub

Die Veröffentlichung übernimmt `scripts/publish_signed_release.py` über den kurzlebigen, repositorygebundenen GitHub-Actions-Token. Diesen Token erhält ausschließlich der Veröffentlichungsjob; auf den Zielservern wird er nicht benötigt und nicht hinterlegt. Der Job prüft den erfolgreichen frischen VM-Test und die unveränderten CI-Artefakte, übernimmt das lokal signierte Manifest und stellt das Archiv reproduzierbar wieder her. Veröffentlichung erfolgt nur bei bytegleicher Prüfsumme und gültiger Signatur. Bestehende Releases werden nicht ersetzt. Danach prüft eine weitere frische VM den tatsächlichen öffentlichen GitHub-Befehl ohne Token im Gast.
