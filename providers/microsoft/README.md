# Microsoft – aktueller FCA-Stand

Der Stufe-B-Entwicklungszweig verwendet das offizielle REST-Inventar und Rclone 1.75.2 für das Standard-OneDrive. Die automatisch ermittelte Drive-ID und der Typ Personal/Business werden in einer getrennten verschlüsselten Kontokonfiguration gespeichert. Rclone besitzt keinen öffentlichen Steuerport. Vor einer Kopie werden Objekt-ID, danach Version und verfügbare Quellhashes geprüft. Outlook-Kalender bleiben beim bestehenden REST-Adapter mit festgelegtem Zeitraum.

Die Webanmeldung behält FCA-PKCE, einmaligen State sowie Benutzer-/Sitzungs-/Fall-/Kontobindung und verwendet eine eigene einmalig administrierte Web-App. Keine gemeinsame fremde Registrierung und kein Device-Code-Standard. Angeforderte Berechtigungen sind lesend. Während einer Dateisitzung ist Rclone alleiniger Token-Refresh-Eigentümer; rotierte Tokens bleiben verschlüsselt erhalten und werden synchronisiert.

**Behoben:** pauschale Wiederholung von `accessDenied` und fehlender Quellhashvergleich. SHA1, QuickXorHash und CRC32 werden soweit geliefert geprüft; fehlende unterstützte Werte ausdrücklich ausgewiesen. Lokale SHA-256 bleibt erhalten.

**Getestet:** synthetische Personal-/Business-Konfiguration, echte lokale Rclone-Kopien mit simulierten Anbieter-Metadaten, Hashfehler, Token-/Kontotrennung und Browser-Rücksprung. Bestehende Kalender- und Weiterleitungstests erhalten. **Offen:** reale Privat-/Geschäftskonten, tatsächlicher Microsoft-Download/Refresh und Mandantenrichtlinien. Weitere Drives und SharePoint werden noch nicht eigenständig inventarisiert. Geprüfte Codeversion b8ac146 nach erfolgreicher CI in die Laborcontainer übernommen; weitere Codekorrekturen nur nach ihrem eigenen grünen CI-Nachweis im PR.

[Stufe-B-Status](../../docs/stufe-b-status.md) · [Privates HTTPS und erster Test](../../docs/private-https-oauth.md) · [Unterstützter Umfang](../../docs/cloud-acquisition.md).
