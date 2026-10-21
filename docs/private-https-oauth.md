# Privates HTTPS und Browseranmeldung

## Gewählter Weg

Ermittler-PC → bestehendes LAN/WireGuard → intern aufgelöster HTTPS-Name → FCA. Google/Microsoft werden vom Browser direkt aufgerufen. Der Rücksprung geht vom Browser zur privaten FCA-Adresse; die autorisierten Übertragungen laufen anschließend auf dem Server. FCA braucht dafür keine öffentliche Eingangsfreigabe und keine Zusatzsoftware auf dem PC. Keine öffentlich erreichbare OAuth-Zwischenstelle.

`fca.example.org` ist ausschließlich ein konfigurierbarer Platzhalter. Die echte Domain wird später festgelegt. Es wurden keine externen Einträge, Zertifikate oder Apps eingerichtet.

## DNS und Zertifikate – nur nach Freigabe

Der Administrator legt eine Subdomain einer kontrollierten, registrierbaren Domain fest. Interner DNS löst sie auf die private VM auf; WireGuard muss diesen Resolver und die Route bereitstellen. Kein öffentlicher A-/AAAA-Eintrag und kein Portforwarding zur FCA-VM erforderlich. Bereits vorhandene andere Domain-Dienste bleiben unverändert.

Für DNS-01 werden zeitweise TXT-Werte unter `_acme-challenge.<FCA-NAME>` veröffentlicht. Die Zertifikatsstelle prüft DNS, nicht den Webserver. Namen öffentlich ausgestellter Zertifikate werden üblicherweise in Certificate-Transparency-Protokollen sichtbar; das veröffentlicht nicht den FCA-Dienst. [Let’s Encrypt DNS-01](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge).

Empfehlung: vorhandene zentrale Zertifikatsverwaltung beziehungsweise ein administrierter ACME-Client mit getesteter DNS-Automatisierung. DNS-Zugangsdaten gehören nicht in die FCA-Anwendung oder Ermittleroberfläche. Möglichst auf die Challenge begrenzte Rechte oder deren Delegation; falls IONOS das im gewählten Vertrag nicht ermöglicht, Schlüssel auf einem gesondert administrierten Erneuerungssystem halten. IONOS-API-Zugang und genaue Automatisierung erst nach Freigabe prüfen. Keine generischen Zonenupdates, die bestehende Einträge anderer Dienste ersetzen. [IONOS DNS API](https://developer.hosting.ionos.com/docs/dns).

Eine einmalige manuelle TXT-Prüfung ist ein möglicher Laborschritt, aber keine wartungsfreie Erneuerung. Certbot `--manual` benötigt für automatische Erneuerung passende Hooks. Nach Erneuerung: Schlüsselrechte und Zertifikatskette prüfen, `nginx -t`, kontrolliertes Reload statt Hostneustart, Ablaufüberwachung und Erneuerungsprobe. [Certbot Erneuerung](https://eff-certbot.readthedocs.io/en/stable/using.html#renewal-with-the-manual-plugin).

Eine interne CA kann technisch genügen, wenn Browser und Betriebssystem der Ermittler-PCs der Kette vertrauen und der DNS-Name im Zertifikat passt. Das ist eine technische Bewertung des browserseitigen Rücksprungs, **kein durchgeführter Google-Akzeptanztest**. Sie ersetzt weder Googles Domainregeln noch eine App-Verifizierung. Eine öffentlich vertraute DNS-01-Kette vermeidet eine zusätzliche Zertifikatsverteilung auf den PCs und ist daher fürs Labor bevorzugt.

Der vorbereitete Generator führt keine Installation aus. Nur für Administratoren, mit eigenen Installationswerten:

```sh
python3 scripts/prepare_private_https.py \
  --host fca.example.org --listen-address 10.20.0.5 \
  --allow 10.20.0.0/24 --allow 10.77.0.0/24 \
  --output .local/https-review
```

Ergebnis: `plan.json`, `nginx.conf`, `origin.env`. Private Beispieladressen sind keine Vorgabe für ein Behördennetz. Der Plan bindet HTTPS ausdrücklich an eine private Adresse, erlaubt nur angegebene Netze und setzt die gleiche Origin wie FCA. IPv6-/WireGuard-Regeln müssen zum tatsächlichen Netz passen. Der alte Labor-Bootstrap `configure-https.sh` erzeugt eine IP-Labor-CA und ist **nicht** das Installationsskript für diesen neuen Domainbetrieb.

## Google – einmalige Administration

Nach separater Freigabe:

1. Eigenes Google-Cloud-Projekt verwenden, Drive API sowie bei gewünschtem Kalenderzugriff Calendar API aktivieren. Keine gemeinsame Rclone-Google-ID.
2. Fürs Labor externe App im Testmodus und ausdrücklich freigegebenen Testnutzer eintragen. Aktuell fordert FCA die lesenden Scopes `drive.readonly` und `calendar.readonly` zusammen an; der reine Drive-Test darf daraus keine geprüfte Kalenderfunktion ableiten.
3. OAuth-Client **Webanwendung**, exakt `https://<FCA-NAME>/api/oauth/callback` als Rückkehradresse. Kein Desktop-Client für diesen Webablauf, kein Implicit-/OOB-Verfahren. Client-ID und Secret ausschließlich als Administrator in FCA-Einstellungen hinterlegen.
4. `FCA_PUBLIC_ORIGIN`, Nginx, DNS und Zertifikat auf denselben Namen abstimmen. Eine Umstellung macht eine neue FCA-Anmeldung am neuen Namen nötig. Bestehende Cookies werden nicht auf andere Hosts übertragen. Callback-Datei `oauth-callback.js` mit ausliefern.
5. Tatsächliche Erreichbarkeit über WireGuard, Zertifikatsvertrauen ohne Browserwarnung, geschützte Rückkehrseite und Registrierung prüfen. Erst dann den persönlichen Google-Test freigeben lassen.

Google erlaubt normale Web-Rückkehradressen nicht als rohe private IP; ein DNS-Name muss die URI-Regeln erfüllen. Domain-Eigentum wird insbesondere für autorisierte Domains/Brand-Verifizierung über Google Search Console nachgewiesen; verlangt die Console diesen Nachweis bereits früher, vor dem Test erledigen. DNS-01-Zertifikatsnachweis und Google-Domainverifizierung sind getrennte Vorgänge. [Google Web-URI-Regeln](https://developers.google.com/identity/protocols/oauth2/web-server#uri-validation), [Domain-/Brand-Verifizierung](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification).

Testmodus: höchstens 100 eingetragene Testnutzer; Drive-Autorisierung und entsprechende Refresh-Tokens laufen nach sieben Tagen ab. Für beliebige externe Ermittlungskonten ist das keine Dauerlösung. [Google App-Zielgruppe](https://support.google.com/cloud/answer/15549945?hl=en).

`drive.readonly` ist eingeschränkt („restricted“). Für externen Behördenbetrieb sind zulässiger Einsatzzweck, Produktionsstatus, erforderliche Verifizierung und Ausnahmen zu klären; serverseitige Verarbeitung kann eine jährliche externe Sicherheitsbewertung erfordern. Eine intern erreichbare FCA-Installation ist keine automatische Ausnahme für fremde Privatkonten. Informations-/Datenschutzseiten für die App-Verifizierung können öffentlich erforderlich sein; FCA selbst bleibt privat. [Scope-Einstufung](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [Restricted-Verifizierung](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification).

## Erster Google-Test – persönliche Schritte nach Freigabe

1. Ein getrenntes Browserprofil oder privates Fenster öffnen und **FCA darin** über den neuen HTTPS-Namen aufrufen. FCA und Anbieteranmeldung im selben Fenster/Tab-Kontext durchführen; sonst fehlt die Sitzungszuordnung.
2. Fall öffnen/anlegen → Cloud hinzufügen → Google → freie Bezeichnung → Anmelden.
3. Das vorbereitete Google-Konto auswählen, angezeigte App und Rechte prüfen und persönlich zustimmen. MFA normal bestätigen. Keine Codes oder Tokens kopieren.
4. Nach der Rückkehr in denselben Fall Sicherung starten → Google Drive. Für die erste Prüfung nur ein vorbereitetes Konto mit kleinem, bekanntem synthetischem Bestand in „Meine Ablage“ nutzen; dieser Lauf erfasst den gesamten zugänglichen Standardbereich.
5. Dateiliste, Exportkennzeichnung, übertragene und geprüfte Dateien sowie SHA-256-Bericht mit dem bekannten Bestand vergleichen. Testabbruch/Wiederaufnahme separat vereinbaren. Größere Downloads erst nach Speicherprüfung.

Am Ende FCA abmelden, privates Fenster vollständig schließen beziehungsweise das getrennte Profil abmelden. Ein Cloud-Login kann Sicherheitsbenachrichtigungen auslösen und ist nicht unsichtbar. Keine Zugangsdaten in Supportnachweise, Screenshots oder Git übernehmen.

## Microsoft-Test – später separat

Administrator registriert eine passende Web-App für gewünschte Privat-/Geschäftskonten, exakte HTTPS-Rückkehradresse und delegierte lesende Rechte `Files.Read Calendars.Read User.Read` plus `offline_access`. Mandantenrichtlinien und gegebenenfalls Adminzustimmung prüfen. Danach derselbe FCA-Ablauf mit OneDrive, zunächst vorbereitetes Privatkonto, anschließend gesonderter Microsoft-365-Testmandant. Rclone übernimmt das bereits durch FCA autorisierte Token; weder eine fremde gemeinsame App noch Device Code ist Standard. Quellhashvergleich und lokale SHA-256 mit bekanntem Testbestand prüfen. [Microsoft Rückkehradressen](https://learn.microsoft.com/en-us/entra/identity-platform/reply-url).

## Alternative ohne Domain

Ein administrierter lokaler SSH-Tunnel bleibt eine bewertete Alternative. PC-, VM- und Container-Loopback sind getrennt; die Browserseite startet keinen Tunnel. Ohne vorinstallierten und zentral vorbereiteten Client ist „nur Browser, keine Installation, kein Administrator am PC“ nicht nachgewiesen. Der fixe Rclone-Loopback-Port und fehlendes PKCE seines nativen Ablaufs sprechen gegen ein unverändertes Durchreichen. Keine manuelle Tokenkopie und kein öffentlicher Proxy. Ein Windows-Helfer würde erst nach nachgewiesenem Bedarf und ausdrücklicher Zustimmung entwickelt. Diese Alternative blockiert den bevorzugten HTTPS-Weg nicht.
