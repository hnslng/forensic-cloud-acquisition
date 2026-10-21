# Cloud-Sicherungen – Version 0.5.0

Stand: 21.10.2026. Implementierte Laborversion, keine Behauptung einer bereits erfolgten Echtkonto-Abnahme. Die freigegebene dunkelblaue Oberfläche und die breiten Cloud-Karten bleiben erhalten.

## Bedienung

1. **Fall anlegen**: Fallnummer, Fallbezeichnung und Bearbeiter eingeben; **Fall starten**.
2. **+ Cloud hinzufügen**: Anbieter wählen, freie Kontobezeichnung vergeben. Mehrere Konten desselben Anbieters sind möglich.
3. **Anmelden**: iCloud mit regulärer Apple-ID, Passwort und gegebenenfalls Apple-Bestätigung. Google/Microsoft öffnen ihre eigene Anmeldeseite. Keine Anbieterpasswörter im Chat eingeben.
4. **Sicherung starten**: Datenbereich auswählen. Bei iCloud optional einen relativen Ordner-/Albumpfad eingeben; leer bedeutet den gesamten vom Adapter sichtbaren Bereich. Für Outlook den angezeigten UTC-Zeitraum festlegen (höchstens zehn Jahre je Lauf).
5. Start bestätigen. Der serverseitige Dienst arbeitet auch bei geschlossenem Browser. Die Cloud-Karte zeigt den echten Auftragsstatus, übertragene Bytes, geprüfte Dateien und gemessene Geschwindigkeit. Eine Restzeit ist eine Schätzung und wird nur bei bekanntem Gesamtumfang angezeigt.
6. **Pausieren** hält den Auftrag an. **Fortsetzen** nimmt pausierte oder fehlgeschlagene Aufträge wieder auf. Nach einem Dienst-/VM-Neustart werden zuvor laufende Aufträge automatisch wieder aufgenommen; ausdrücklich pausierte Aufträge bleiben pausiert.
7. **Sicherungsläufe** zeigt frühere Läufe dieses Kontos sowie die geschützten Downloads von Sicherungsbericht und Dateiliste mit SHA-256-Prüfsummen.
8. Parallelität und Anbieteranwendungen werden unter **Einstellungen → Technischer Status** durch einen Administrator eingerichtet.

„Abgeschlossen“ bedeutet: Das erfolgreich inventarisierte, ausgewählte und über die jeweilige Schnittstelle sichtbare Inventar wurde vollständig übertragen und lokal geprüft; keine ausgelassenen Inventarobjekte oder fehlgeschlagenen Dateien. Das ist keine Garantie für ein vollständiges Cloud-Konto, gelöschte Inhalte oder eine atomare Momentaufnahme. Fehler und tatsächlich ausgelassene Objekte führen zu „Unvollständig“ oder „Fehlgeschlagen“.

## Anbieterstatus und definierter Umfang

| Anbieter/Bereich | Implementiert | Praktische Echtkonto-Abnahme | Abgrenzung |
| --- | --- | --- | --- |
| iCloud Drive | Anmeldung/2FA, Ordneransicht, rekursive Inventarisierung und Download | Offen: vorbereitetes Konto muss angemeldet werden | Sichtbare aktuelle Objekte über rclone 1.75.2; keine öffentliche allgemeine Apple-Download-API. ADP/Webfreigabe, geteilte Ordner und Apple-Änderungen können Zugriff einschränken. |
| iCloud Fotos | Bereichsansicht, Inventarisierung und Download der vom Adapter angebotenen Fotoansicht | Offen | Keine Zusicherung aller Originalvarianten, RAW/Live-Photo-Komponenten, Bearbeitungen oder aller Mediatheksmetadaten; Einschränkungen des Adapters gelten. |
| Google Drive | Offizielles OAuth mit PKCE/Offline-Zugriff, persönliche Stammordnerstruktur, Binärdateien und Workspace-Exporte | Offen: registrierte App und Testkonto fehlen | „Meine Ablage“, keine eigenständige Erfassung geteilter Ablagen oder „Mit mir geteilt“, sofern nicht unter dieser Struktur sichtbar. Dokumente→DOCX, Tabellen→XLSX, Präsentationen→PPTX, Zeichnungen→PDF. Originaldateiformat dieser nativen Objekte ist kein herunterladbares Binäroriginal. Exportgrenze der API beachten. Nicht unterstützte Workspace-Typen/Verknüpfungen werden protokolliert. |
| Google Kalender | Kalenderliste, sämtliche abrufbaren Ereignisse mit Serienregeln, Ausnahmen und Löschmarkierungen als paginierte Anbieter-JSON-Daten | Offen: App/Testkonto fehlen | Nur in der Kalenderliste verfügbare Kalender. Keine Terminanhänge als Binärdateien; keine Garantie für bereits dauerhaft gelöschte Ereignisse. |
| Microsoft OneDrive | Offizielles OAuth mit PKCE/Offline-Zugriff, Standardlaufwerk, rekursive Dateien/Ordner | Offen: registrierte App und Testkonto fehlen | Keine mandantenweite SharePoint-Sammlung, fremden Laufwerke, historischen Versionen, Papierkörbe oder externen Verknüpfungsziele. Paketobjekte werden ausdrücklich ausgelassen und führen zu „Unvollständig“. |
| Outlook-Kalender | Kalenderliste und `calendarView` im ausdrücklich gewählten UTC-Zeitraum als paginierte Anbieter-JSON-Daten | Offen: App/Testkonto fehlen | Einzeltermine und expandierte Serien/Ausnahmen innerhalb des Zeitraums. Keine Anlagen-Binärdateien, keine unbeschränkte Vergangenheit/Zukunft, keine zusätzliche delegierte Postfachberechtigung. |

Weitere Kategorien wurden berücksichtigt: Dateifotos/-videos sind normale Drive-/OneDrive-Dateien; iCloud Fotos hat eine eigene Kategorie. Gmail/Outlook-Mail, Kontakte, Google Fotos, iCloud-Mail/-Kalender/-Kontakte, Gerätebackups, frühere Dateiversionen und Papierkörbe sind in dieser Version **nicht implementiert**. Keine vollständige Kontosicherung behaupten. Bei Google Workspace sind nicht exportierbare Objekte einschließlich Google Vids/Forms/Shortcuts ausdrücklich als Lücke zu behandeln; kein Zugriffsschutz wird umgangen.

## Anbieteranwendungen einrichten

Die Anwendung enthält absichtlich keine fremden Client-IDs oder mitgelieferten Anwendungsgeheimnisse. Ein Administrator registriert die jeweilige **Webanwendung** beim Anbieter und trägt unter Einstellungen Anwendungs-ID, Anwendungsschlüssel und die exakt angezeigte Rückkehradresse ein. Diese Werte werden mit dem externen FCA-Masterschlüssel verschlüsselt außerhalb der Datenbank abgelegt. Vorhandene Konfiguration wird nicht als Geheimtext zurückgegeben.

- Google: Drive API und Calendar API aktivieren. Einwilligungsbildschirm/Testnutzer einrichten; delegierte Scopes `drive.readonly` und `calendar.readonly`, Offline-Zugriff. Für dauerhaften/breiten Betrieb gelten Googles Veröffentlichungs-/Prüfanforderungen; im Testmodus können Refresh-Tokens befristet sein. Google erlaubt eine private IP-Adresse wie `10.0.1.189` nicht als normale Web-Redirect-URI. Dafür ist eine vom Anbieter zugelassene HTTPS-Domain mit passendem Zertifikat und exakter FCA-Origin-Konfiguration erforderlich. Keine öffentliche Portfreigabe ist für ausgehende API-Anfragen nötig; DNS/TLS/Origin müssen vor einer echten Google-Abnahme abgestimmt werden.
- Microsoft: Webanwendung für die gewünschten Kontoarten registrieren, Client-Geheimnis, exakt passende HTTPS-Rückkehradresse; delegierte Scopes `offline_access Files.Read Calendars.Read User.Read`. Mandantenrichtlinien/Administratorzustimmung können erforderlich sein. Keine SPA-/Implicit-Konfiguration verwenden.
- Rückkehradresse: `<FCA_HTTPS_ORIGIN>/api/oauth/callback`. Die bestehende private Laboradresse wird nicht eigenmächtig verändert.
- Anmeldungen nutzen zufälligen einmaligen State, PKCE S256, Benutzer-/Fall-/Kontobindung und zehn Minuten Ablauf. Die Rückkehrseite entfernt Code/State aus der sichtbaren URL und tauscht sie per geschütztem POST aus. Nginx protokolliert `/api/` einschließlich Rückkehradresse nicht; Uvicorn-Zugriffslogs sind aus.

## Verzeichnisse und Unveränderlichkeit

Konfiguriert ist der separate Datenträger `/srv/fca/evidence`, im Container `/evidence`:

```text
FCA-Sicherungen/
  2026-00125__<eindeutige-Fall-UUID>/
    iCloud_1/
      Lauf_<Sicherungs-UUID>/
        Daten/<abgebildete Cloud-Ordnerstruktur>
        _FCA/
          Sicherungsbericht.json
          Dateien.jsonl
          Ordner/<Quellordner-Metadaten>.json
          temporär/<Datei-ID>.part
    iCloud_2/
    iCloud_Fotos_1/
    Google_Drive_1/
    Google_Kalender_1/
    OneDrive_1/
    Outlook_Kalender_1/
```

Fallnummern werden auf sichere Pfadbestandteile normalisiert und immer mit der vollständigen Fall-UUID kombiniert. Die bestehende Datenbank-Eindeutigkeit der Fallnummer bleibt erhalten. Unterschiedliche Fallnummern, die nach Normalisierung gleich aussehen, erhalten dennoch getrennte Verzeichnisse. Anbieterordner werden pro Fall transaktional nummeriert. Die frei gewählte Kontobezeichnung bleibt davon unabhängig.

Jeder Lauf hat eine neue UUID und ein neues Verzeichnis. Cloud-Datei-/Ordnernamen erhalten einen stabilen, aus ihrer Quellkennung abgeleiteten Zusatz; dadurch bleiben auch doppelte Namen und Unterschiede in Groß-/Kleinschreibung getrennt. Die Eltern-/Kindstruktur bleibt erhalten. Ursprüngliche Namen, IDs, Zeitangaben und Metadaten stehen im Manifest bzw. den Ordner-Metadaten. Daten liegen getrennt von FCA-Berichten; Quelldateien namens „Dateien.jsonl“ kollidieren nicht mit dem Bericht.

Zunächst wird ausschließlich in `.part` geschrieben. Nach erfolgreichem Anbieterabruf, Größen-/gegebenenfalls Anbieterprüfsummenprüfung und lokalem SHA-256 wird der Hash dauerhaft protokolliert. Eine zweite lokale SHA-256-Lesung prüft die Datei vor der atomaren Übernahme ohne Überschreiben (`link`, Dateisystem-Fsync). Erst danach gilt sie in der Warteschlange als abgeschlossen. Bei Neustart werden bereits fertige Dateien erneut gegen ihren gespeicherten SHA-256 geprüft. Abweichungen werden nicht durch Überschreiben repariert. Fehlgeschlagene Einzeldateien bleiben nachvollziehbar.

**Wiederaufnahme erfolgt auf Dateiebene:** Erfolgreiche Dateien werden beibehalten und geprüft; eine nicht vollständig übertragene Datei beginnt erneut bei Byte 0. Diese Version verspricht keine anbieterübergreifende HTTP-Range-/Bytefortsetzung. Das verhindert die Vermischung von Teilständen einer zwischenzeitlich veränderten Quelldatei. Für sehr große Einzeldateien kann dies erneuten Datenverkehr verursachen.

## Warteschlange, Parallelität und Ressourcen

- Dateierfassung und Dateiübertragung laufen parallel. Die Erfassung schreibt einzeln bestätigte Dateien in die dauerhafte Warteschlange; die Übertragung verarbeitet bereits erfasste Dateien in Erfassungsreihenfolge. Eine zwischenzeitlich leere Warteschlange beendet den Auftrag nicht, solange noch Dateien gesucht werden. Fehler bei der Erfassung verhindern einen vollständigen Erfolgsstatus.
- Die Cloud-Karte aktualisiert alle zwei Sekunden erfasste und geprüfte Dateianzahl, Datenmenge und Geschwindigkeit. Solange die Erfassung läuft, werden weder Gesamtprozent noch Restzeit vorgetäuscht.
- PostgreSQL speichert Aufträge, Inventar, Dateizustand, Versuche, Hashes und Fortschritt dauerhaft. Ein separater Worker hat keinen öffentlichen Port.
- Ein Datenbank-Leader-Lock verhindert doppelte Koordinatoren; pro Konto ist höchstens ein aktiver/pausierter Lauf zulässig. Gleichzeitig laufen auf der Test-VM höchstens zwei Konten, je maximal vier Dateien. Administratoren können innerhalb dieser Grenzen reduzieren. Änderungen greifen ab der nächsten Übertragungswelle bzw. Kontoaufnahme.
- Kleine feste Übertragungswellen und 256-KiB-Puffer begrenzen den Speicherbedarf. Der Worker hat 512 MiB Speichergrenze und eine CPU; API/DB bleiben separat begrenzt. rclone verwendet pro Konto einen privaten Unix-Socket und keine öffentliche Steueradresse.
- Temporäre HTTP-/Netzfehler: bis fünf Einzeldateiversuche mit Wartezeit. HTTP 429/503 und `Retry-After` (Sekunden oder HTTP-Datum) werden berücksichtigt. Nach Drosselung/temporären Übertragungsproblemen reduziert sich die nächste Welle konservativ auf eine Datei. rclone nutzt zusätzlich seinen Anbieter-Pacer und begrenzte Low-Level-Wiederholungen.
- Reserviert bleiben standardmäßig 2 GiB, mindestens 1 GiB per API. Prüfung vor Auftrag und Dateibeginn, bei Inventarisierung und laufend während Übertragung. Knappheit führt zu Pause, nicht zu Erfolg. Bereits erfasste Daten bleiben erhalten.
- Verfügbarer VM-RAM, Container-Speicher, freier Datenträger und Last werden beobachtet. Unter 150 MiB verfügbarem RAM oder oberhalb 85 % des jeweiligen Containerlimits wird ein Lauf pausiert. Die kleinen synthetischen Prüfungen ersetzen keinen Lasttest mit großen Cloud-Beständen.
- Entzug der Bearbeitungsberechtigung bzw. Deaktivierung des Auftraggebers stoppt weitere Verarbeitung. Leser dürfen keine Sicherung starten/fortsetzen. Protokolle/Berichte bleiben über die Fallberechtigung geschützt.

## Forensischer Bericht

Bericht/Manifest enthalten Fallnummer/-ID, Bearbeiter, Anbieter und Kontokennung, Beginn/Ende, Zugriffsmethode, gewählte Kategorie/Umfang, Sicherungs-ID, Dateizahl, Bytes, Quellmetadaten, lokale SHA-256, Fehler und Lücken. Anbieteridentitäten werden nur in geschützten Falldaten gespeichert; Passwörter, Tokens, OAuth-Codes, Cookies und signierte Downloadadressen gelangen nicht in Berichte oder Audit-Details. Das Manifest selbst erhält einen SHA-256 im Bericht. Dies ist Integritätsprüfung, keine digitale Signatur oder Herkunftsbestätigung des Anbieters.

## Prüfungen und ausstehende Abnahme

Automatisiert werden reale PostgreSQL-/HTTP-/Chromium-Abläufe mit synthetischen Konten geprüft; Providerantworten sind in diesen Tests markierte Simulationen. Ein echter lokaler TCP-Abbruch, echte Worker-Prozesse einschließlich Abbruch/Neustart sowie der gepinnte rclone-Transfer im netzlosen Container werden zusätzlich geprüft. Das beweist keine erfolgreiche Apple-, Google- oder Microsoft-Anmeldung.

Eine praktische Anbieterabnahme benötigt ausdrücklich freigegebene Konten und, bei Google/Microsoft, die jeweiligen App-Registrierungen. Keine echten Zugangsdaten wurden angefordert, in Git abgelegt oder für Screenshots verwendet. Größere Downloads erst nach erneutem Speicher-/Ressourcencheck. Die abgeschlossene UI-Gestaltung wird dabei nicht erneut verändert.

## Primärquellen

- [Google OAuth-Webserver-Verfahren](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google Drive Downloads und Exporte](https://developers.google.com/workspace/drive/api/guides/manage-downloads)
- [Google Kalender: Ereignisliste](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)
- [Microsoft OAuth Authorization Code und PKCE](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)
- [Microsoft Graph: Drive-Dateiinhalt](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0)
- [Microsoft Graph: Kalenderansicht](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0)
- [Microsoft Graph Drosselung](https://learn.microsoft.com/en-us/graph/throttling)
- [rclone iCloud Drive/Fotos](https://rclone.org/iclouddrive/) – gepinnter Quellstand aus Phase 2 bleibt maßgeblich.

## Bereitstellung und Nachweise

Version 0.5.0 ist auf VM 105 bereitgestellt. **66 automatisierte Prüfungen und GitHub CI erfolgreich**, bestehende Daten/Dateien unverändert, alte und neue Datenbankversion sowie Dateiarchive tatsächlich getrennt wiederhergestellt. Einzelheiten, Ressourcen und synthetische Desktop-/Mobilaufnahmen: [Prüf- und Bereitstellungsnachweis](cloud-acquisition-validation.md). Für die tägliche Bedienung: [Kurzanleitung](kurzanleitung.md).
