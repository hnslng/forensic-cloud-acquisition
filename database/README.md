# Datenbank

PostgreSQL 17 ist zunächst die Infrastrukturgrundlage. Der Bootstrap-Account ist
nur für Einrichtung und Abnahme bestimmt. In Phase 1 folgen getrennte Rollen
für Migrationen, API und Worker mit minimalen Berechtigungen.

`migrations/0001_bootstrap.sql` wird einmal gegen eine neue Datenbank angewandt.
Ein zweiter Lauf muss fehlschlagen, statt einen falschen Migrationsstand zu
kaschieren. Der spätere Migrationsrunner verwaltet Reihenfolge und Prüfsummen.

```sh
docker compose --env-file /etc/fca/compose.env up -d --wait
docker compose --env-file /etc/fca/compose.env exec -T database \
  psql -v ON_ERROR_STOP=1 -U fca_bootstrap -d fca < migrations/0001_bootstrap.sql
```

Diese Kommandos wurden auf der noch nicht angelegten VM nicht ausgeführt.
