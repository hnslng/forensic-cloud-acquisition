# Datenbank

PostgreSQL 17 ist die Infrastrukturgrundlage. Der Bootstrap-Account ist nur für
Einrichtung und Abnahme bestimmt. `fca_migrate` besitzt die Anwendungstabellen;
`fca_api` hat begrenzte Laufzeitrechte und darf Audit-Ereignisse weder ändern
noch löschen. Eine gesonderte Worker-Rolle folgt mit Phase 3.

`migrations/0001_bootstrap.sql` wird einmal gegen eine neue Datenbank angewandt.
Ein zweiter Lauf muss fehlschlagen, statt einen falschen Migrationsstand zu
kaschieren. Der spätere Migrationsrunner verwaltet Reihenfolge und Prüfsummen.

```sh
docker compose --env-file /etc/fca/compose.env up -d --wait
docker compose --env-file /etc/fca/compose.env exec -T database \
  psql -v ON_ERROR_STOP=1 -U fca_bootstrap -d fca < migrations/0001_bootstrap.sql
```

Der Bootstrap ist auf VM 105 bereits erfolgreich ausgeführt. Nicht erneut auf
der Arbeitsdatenbank anwenden. Weitere Migrationen werden kontrolliert über
`scripts/configure_phase1_database.py` eingespielt; bestehende Rollen und
Passwörter werden nicht stillschweigend ersetzt. Für isolierte Tests wird eine
eigene Datenbank erstellt und anschließend entfernt.
