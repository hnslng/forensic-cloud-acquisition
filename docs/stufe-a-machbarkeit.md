# Stufe A – Machbarkeit von Google Drive und OneDrive

> Historischer Befund aus Commit `4553cc4`. Der aktuelle Entwicklungsstand steht unter [Stufe B](stufe-b-status.md). Die damaligen Befundprüfungen sind mit dem damaligen Code zu reproduzieren; behobene Fehler müssen heute nicht mehr reproduzierbar sein.

Stand: 21.10.2026. **Stufe B ist nicht freigegeben und wurde nicht begonnen.**

Geprüft wurden das bestehende Repository, die gepinnte Rclone-Version 1.75.2, aktuelle Anbieterunterlagen und die Test-VM ausschließlich lesend. Lokale Versuche verwenden synthetische Dateien und einen simulierten OAuth-Anbieter. Es erfolgten keine echten Cloud-Anmeldungen, keine Bereitstellung und keine Änderung an Beweisdaten oder anderen Systemen.

## Die acht Antworten

| Frage | Ergebnis |
|---|---|
| 1. Google ohne Domain? | **Technisch ja:** eigene Desktop-App und Loopback-Rückkehradresse. **Mit entferntem FCA-Server und nur Browser allein nicht vollständig:** Am PC muss ein lokaler Listener oder ein vorbereiteter Tunnel vorhanden sein. Der heutige FCA-Webablauf unterstützt diese Variante noch nicht. [Google](https://developers.google.com/identity/protocols/oauth2/native-app) |
| 2. Microsoft ohne eigene App-Registrierung? | **Rclone bietet das grundsätzlich über seine gemeinsame App an.** Ein erfolgreicher Login mit einem echten Konto wurde nicht geprüft. Das bestehende FCA verlangt derzeit eine eigene App; die Rclone-Alternative ist nicht integriert. Für Behörden sind eigene, kontrollierte Registrierungen vorzuziehen. [Rclone](https://rclone.org/onedrive/#getting-your-own-client-id-and-key) |
| 3. Zusatzsoftware am PC? | Bei FCA unter einem administrierten HTTPS-Domainnamen **keine**. Ohne Domain ist ein vorhandener, zentral vorbereiteter SSH-Client eine mögliche Alternative. Ob dies ohne Installation und Benutzer-Administratorrechte auf den Ziel-PCs funktioniert, ist noch zu prüfen. Ein neues Windows-Programm ist nicht zwingend und wurde nicht entwickelt. |
| 4. Einmalige Administratoreinstellungen? | Google-Projekt, Drive API, eigener OAuth-Client und Freigabestatus; Microsoft vorzugsweise eigene App mit lesenden Rechten. Zusätzlich entweder interner Domainname mit vertrauenswürdigem HTTPS oder ein abgesicherter Tunnelbetrieb. Nicht je Konto neu, keine Tokens oder Befehle für Ermittler. |
| 5. Welche Inhalte? | Heute: Google „Meine Ablage“ mit unterstützten Workspace-Exporten; OneDrive-Standardlaufwerk. Rclone kann zusätzlich zugängliche geteilte Ablagen und ausgewählte SharePoint-Bibliotheken erschließen; deren Ermittlung und Abbildung in FCA gehören zu Stufe B. Kalender benötigen weiterhin die vorhandenen REST-Adapter. |
| 6. Welche Grenzen? | Keine Gesamtkonto-Vollständigkeit zusichern. Fehlende Berechtigungen, ausgelassene Bereiche und offene Inventare getrennt ausweisen. Zwei bestätigte aktuelle Lücken: pauschale 403-Wiederholung und fehlender OneDrive-Quellhashvergleich. Der native Rclone-OAuth-Ablauf sendete im Versuch kein PKCE. |
| 7. Realistische Leistung der VM? | **Noch kein belastbarer Cloud-MB/s-Wert.** Der vorhandene Lauf ist pausiert; ein Lasttest auf der VM wäre mehr als die freigegebene lesende Bestandsaufnahme. Gemessen: ca. 1,34 GiB RAM verfügbar, 30,73 GiB frei auf dem Sicherungsdatenträger, davon ca. 28,73 GiB nach Reserve nutzbar. 4 Dateien / 2 Konten bleiben bestehen. |
| 8. Empfehlung für Behörden? | **Browseroberfläche unter administriertem HTTPS-Namen, eigene Anbieter-Apps, vorhandener FCA-OAuth-/PKCE-Schutz und Rclone als Dateiadapter.** Domainnamen und Einrichtung gehören zum Administrator. Wenn Domainfreiheit zwingend ist, zuerst den zentral vorbereiteten Tunnelbetrieb auf einem freigegebenen Windows-Testplatz prüfen. Keinen Anmeldehelfer auf Verdacht entwickeln. |

## Google-Freigabe ist eine eigene Hürde

Der Testmodus erlaubt bis zu 100 vorab eingetragene Testnutzer; für Drive-Zugriff laufen entsprechende Autorisierungen/Refresh-Tokens grundsätzlich nach sieben Tagen ab. Das ist keine geeignete Dauerlösung für wechselnde, nicht vorab gelistete Ermittlungskonten. [Google: App-Zielgruppe](https://support.google.com/cloud/answer/15549945?hl=en), [Tokenlebensdauer](https://developers.google.com/identity/protocols/oauth2#expiration).

`drive.readonly` ist ein eingeschränkter („restricted“) Scope. Für externen breiten Betrieb sind Produktionsstatus und die erforderliche Verifizierung zu klären. Serververarbeitung kann zusätzlich eine regelmäßig wiederkehrende Sicherheitsprüfung auslösen, sofern keine anwendbare Ausnahme besteht. „Behördenintern eingesetzt“ bedeutet nicht automatisch „Google-interne App“ für fremde Privatkonten. Ein Desktop-Client beseitigt diese Prüfanforderungen nicht. [Scope-Einstufung](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [Verifizierung](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification).

Die gemeinsame Google-ID von Rclone wird laut aktueller Dokumentation 2026 eingestellt. Sie ist keine tragfähige Grundlage. Ein eigener Client ist einmalig einzurichten. Eine konkrete bereits erfolgte Abschaltung wurde ohne echte Anmeldung nicht festgestellt. [Rclone-Hinweis](https://rclone.org/drive/#making-your-own-client-id).

## Ergebnis der praktischen Versuche

- Beide nativen Rclone-Rückkehrabläufe mit **lokalem OAuth-Simulator** erfolgreich; falscher State abgelehnt, Portkonflikt bei gleichzeitigen Anmeldungen nachgewiesen. Kein echter Google-/Microsoft-Login.
- Bestehende FCA-Prüfungen für Benutzer-/Fall-/Kontozuordnung, State, Ablaufzeit, Einmalverwendung und verschlüsselte Ablage lokal erfolgreich. Der bestehende Schutz wird nicht durch einen schwächeren Ablauf ersetzt.
- 17 synthetische Übertragungsläufe mit 1/2/4/8 Dateien je Übertragungspool und 1/2 parallelen Pools; SHA-256-Prüfung aller Zieldateien. Netzwerkabbruch, HTTP 429 und Wiederanlauf eines beendeten Rclone-Prozesses geprüft.
- 11 bestehende Infrastrukturtests lokal erfolgreich. Vorhandene VM-Testnachweise wurden nur gelesen; die produktive Datenbank wurde nicht als Testdatenbank verwendet.

[Technischer Befund, Messgrenzen und erste Testschritte](stufe-a-technik.md). Die Messzahlen sind **lokale Vergleichswerte**, keine Leistungszusage für die FCA-VM.

## Freigabeentscheidung

Stufe A endet hier. Vor einer Integration ist die Anmeldevariante festzulegen. **Stufe B, Änderungen an der VM und echte Cloud-Anmeldungen benötigen die gesonderte Freigabe des Auftraggebers.** Der bereits freigegebene Designstand bleibt bestehen.
