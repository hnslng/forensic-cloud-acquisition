# Architekturentwurf – ab Phase 1 umzusetzen

Dieser Entwurf ist keine Implementierungsbehauptung.

## Komponenten

Privater Browser → HTTPS-Reverse-Proxy → separates Frontend und FastAPI-API.
PostgreSQL speichert Fälle, Identitäten, Berechtigungen, Konten, den freigegebenen
Zugriffsumfang, Aufträge, Dateiinventare und Auditereignisse. Separate
Worker-Prozesse beanspruchen persistente Aufträge über Transaktionen und
`FOR UPDATE SKIP LOCKED`, mit Lease, Heartbeat, Retry und Wiederanlauf.
Die konkrete Implementierung samt Konkurrenz- und Absturztests folgt in Phase 3.

Für das kleine Labor entfällt zunächst ein zusätzlicher Redis-Dienst.
Eine PostgreSQL-basierte Queue verringert den RAM-Bedarf und erlaubt atomare
Auftragsanlage zusammen mit Audit und Freigabe. Netzwerkaufrufe und Downloads
laufen außerhalb von DB-Transaktionen. Verwaiste Leases werden kontrolliert
zurückgewonnen; atomare temporäre Dateischreibvorgänge und idempotente Schritte
verhindern, dass ein Retry unvollständige Dateien als fertig behandelt.

## Trennung und Nachvollziehbarkeit

Technische Pfade verwenden unveränderliche Fall-, Konto- und Sicherungs-UUIDs.
Anzeigenamen und Geschäftszahlen sind keine Pfadbestandteile. Jede API-Abfrage
prüft Identität, Fallmitgliedschaft und Aktion serverseitig. Browser- oder
Worker-übergreifende globale aktive Fälle sind ausgeschlossen. Ein Bearbeiter
wird zusätzlich zur authentifizierten Identität je Sicherung festgehalten.

Vor Providerzugriffen muss eine unveränderlich referenzierte Umfangsfreigabe
vorliegen. Provideradapter dürfen nur den technisch erzwingbaren Teil anbieten.
Kein Gesamtscan eines Kontos, wenn nur ein begrenzter Bereich freigegeben wurde.
Providerfähigkeiten, Einschränkungen und fehlende Bereiche werden ausdrücklich
erfasst; Übertragungsintegrität und Kontovollständigkeit bleiben getrennt.

Dateien werden gestreamt, in temporäre Dateien geschrieben, auf Größe und
verfügbare Providerprüfsummen geprüft, atomar abgeschlossen und mit SHA-256
versehen. Originalpfade bleiben Metadaten und dürfen weder `..`-Traversal noch
Symlink-Zugriffe verursachen. Cloud-native Exporte werden als Konvertierungen
dokumentiert. Ein erfolgreicher Hashlauf beweist keine Kontovollständigkeit.

## Identitätsmodelle

| Modell | Vorteil | Grenze |
|---|---|---|
| A: geschützte Gerätesitzung + Kürzel | Geringste Bedienzeit | Gemeinsame Sicherheitsidentität; nur zusätzlich abgeschottet zulässig |
| B: persönliche lokale Konten | Individuelle Rechte und Zuordnung | Benutzer- und Passwortpflege erforderlich |
| C: zentraler Identitätsanbieter | Zentrale Sperren und Richtlinien | Verfügbarkeit und Behördenanbindung erforderlich |

Im Labor wird in Phase 1 zunächst ein lokaler Administrator mit sicherer
Passwortableitung, serverseitiger Sitzung, CSRF-Schutz und sicherem Cookie
eingerichtet. Keine Standardpasswörter. Authentifizierung wird über einen
austauschbaren Identity-Provider von der fallbezogenen Autorisierung getrennt.
OIDC ist ein möglicher späterer zentraler Einstieg; AD/LDAP benötigen eine
bewusste Integrationsentscheidung. Vor dem produktiven Benutzerkonzept werden
die Modelle dem Auftraggeber zur Entscheidung vorgestellt.

## Deployment und Geheimnisse

Docker Compose mit separatem API-/Worker-Container, PostgreSQL und TLS-Proxy.
Nur der Proxy veröffentlicht HTTPS an einer privaten Adresse. Datenbank und
API erhalten keine externen Ports. Docker-Firewallregeln sind gesondert zu
prüfen, da veröffentlichte Ports übliche Host-Firewalls umgehen können.
Keine Docker-Socket-Mounts, privilegierten Container oder Shellbefehle aus
Benutzereingaben. Runtime- und Migrationsrollen werden getrennt.

Tokens werden mit fallbezogenem Kontext authentifiziert verschlüsselt; der
Hauptschlüssel liegt außerhalb von Datenbank, Backups und Git. Für einen Restore
ist eine gesondert gesicherte Schlüsselkopie erforderlich. Keine Tokens in
Prozessargumenten oder Logs. Bereinigung und erneute Authentifizierung werden
auditiert. Das Entziehen der Worker-Zugangsdaten darf die bereits gesicherten
Dateien und Prüfberichte nicht unzugänglich machen.

Updates verwenden geprüfte, festgeschriebene Images/Versionen, vorab gesicherte
Datenbank und eine ausdrückliche Migrationsstrategie. Code-Rollback ersetzt
keinen Datenbank-Restore. Im Labor werden zuerst kleine synthetische Aufträge
und Neustarts geprüft. Behördliches Deployment bleibt gesondert freizugeben.
