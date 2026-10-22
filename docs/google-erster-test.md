# Google über privates HTTPS: erster Test

FCA verwendet den bestehenden Browserablauf mit PKCE, einmaligem State und
Bindung an die konkrete FCA-Sitzung. Ein Ermittler benötigt keine zusätzliche
Software, keinen SSH-Tunnel und keine manuell kopierten Tokens.

## Einmalig durch den Administrator

1. Einen Namen unter einer eigenen Domain intern auf die FCA-VM auflösen.
   Alle für LAN/WireGuard verwendeten Resolver müssen übereinstimmen. Kein
   öffentlicher Webzugang, kein Portforwarding und kein öffentlicher Proxy.
2. Ein für diesen Namen vertrauenswürdiges HTTPS-Zertifikat einrichten.
   DNS-01 erlaubt dies ohne öffentlich erreichbaren FCA-Webserver. Erneuerung
   samt geprüfter Nginx-Neuladung automatisieren; DNS-Schlüssel ausschließlich
   geschützt in der Administration halten. Zertifikatsnamen werden öffentlich
   in Certificate-Transparency-Protokollen sichtbar.
3. Nginx, `FCA_PUBLIC_ORIGIN` und Rückkehradresse auf denselben Namen abstimmen.
   Änderungen an laufenden Diensten nur nach Freigabe und Sicherung vornehmen;
   einen vorhandenen pausierten Auftrag nicht wiederaufnehmen.
4. Im eigenen Google-Cloud-Projekt Drive API aktivieren. Die aktuelle FCA-Version
   fordert zusätzlich `calendar.readonly` an: dafür auch Calendar API aktivieren.
   Testzustimmung für Kalender ist keine praktische Abnahme der Kalenderfunktion.
5. In Google Auth Platform einen vorhandenen passenden OAuth-Client ergänzen
   oder einen Client vom Typ **Webanwendung** erstellen. Exakte Rückkehradresse:
   `https://<FCA-Name>/api/oauth/callback`. Kein Desktop-Client, kein OOB-Verfahren.
   Für externe Testkonten die Zielgruppe **External / Testing** und den Nutzer
   als Testnutzer eintragen. Gegebenenfalls Domainnachweis in Search Console
   abschließen. Bestehende Clients und deren andere Rückkehradressen erhalten.
6. Client-ID, Client-Secret und Rückkehradresse einmalig in den geschützten
   FCA-Administratoreinstellungen für Google speichern. Keine Geheimnisse per
   Chat, GitHub, Screenshot oder Fallprotokoll übertragen.
7. Namensauflösung, Zertifikatsvertrauen und Rückkehr über den tatsächlichen
   WireGuard-Zugang prüfen. Persönliche Google-Anmeldung erst nach Freigabe.

## Ermittler: anmelden und sichern

1. WireGuard verbinden und FCA unter dem eingerichteten **HTTPS-Namen** öffnen.
   Nach einem Wechsel von IP-Adresse auf DNS-Namen erneut in FCA anmelden.
2. Fall öffnen → **Cloud hinzufügen → Google** → Kontobezeichnung vergeben.
3. Auf der Cloud-Karte **Anmelden** wählen. FCA leitet denselben Browser-Tab
   zu Google und anschließend zurück. Den Tab nicht in ein anderes Profil
   verschieben und keine parallele zweite Anmeldung für dieselbe Karte starten.
4. Google-Konto auswählen, Berechtigungen prüfen, persönlich zustimmen und MFA
   bestätigen. FCA stellt danach den Fall wieder her und zeigt **Verbunden**.
5. **Sicherung starten → Google Drive** wählen. Inventarisierung, Übertragungen
   und Fortschritt laufen serverseitig; der Browser kann anschließend geschlossen
   werden. Für ein zweites Konto eine weitere Google-Karte hinzufügen.

Der erste Test verwendet ein vorbereitetes Konto mit kleinem, bekanntem
synthetischem Bestand in „Meine Ablage“. Vor dem Download freien Speicher
prüfen; anschließend gespeicherte Dateien, Metadaten, Exportformate und
Prüfsummen mit diesem Bestand vergleichen. Bestehende Sicherungen nicht als
Testdaten verwenden.

## Fehler und Grenzen

- `redirect_uri_mismatch`: registrierte Rückkehradresse exakt mit FCA vergleichen.
- „Anmeldung abgelaufen“: erneut auf derselben Cloud-Karte anmelden. State gilt
  zehn Minuten und kann nur einmal verwendet werden.
- Nach Ablehnung der Google-Rechte bleibt das Konto unverbunden; keine
  Erfolgsmeldung und keine automatisierte Tokenkopie.
- Ein externer Google-Testzugang mit diesen Scopes läuft nach sieben Tagen ab,
  einschließlich Refresh-Token. Dann erneut anmelden. Für späteren Behördenbetrieb
  ist die erforderliche Google-Produktions-/Scope-Verifizierung separat zu klären.
- Der aktuelle Drive-Adapter inventarisiert „Meine Ablage“. Shared Drives und
  „Mit mir geteilt“ sind nicht eigenständig vollständig erfasst. Google Docs,
  Sheets und Slides werden exportiert; keine unveränderten Binäroriginale.
- Synthetische Tests ersetzen keine erfolgreiche Anmeldung am echten Anbieter.

Quellen: [Google Web-OAuth und URI-Regeln](https://developers.google.com/identity/protocols/oauth2/web-server#uri-validation),
[Google Testnutzer und Ablauf](https://support.google.com/cloud/answer/15549945?hl=en),
[Let's Encrypt DNS-01](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge).
