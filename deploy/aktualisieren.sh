#!/usr/bin/env bash
# Holt neue Kunden/Änderungen aus Git. Läuft per Cron alle 5 Minuten (richtet einrichten.sh ein).
# - Nur Kunden-Dateien geändert → nichts weiter nötig, die Plattform lädt sie selbst neu.
# - Plattform-Code geändert → Container wird neu gestartet (bzw. neu gebaut bei neuen Abhängigkeiten).
set -euo pipefail
cd "$(dirname "$0")/.."

ZWEIG="${NGC_ZWEIG:-main}"
git fetch --quiet origin "$ZWEIG"
ALT=$(git rev-parse HEAD)
NEU=$(git rev-parse "origin/$ZWEIG")
[ "$ALT" = "$NEU" ] && exit 0

git merge --ff-only --quiet "origin/$ZWEIG"
GEAENDERT=$(git diff --name-only "$ALT" "$NEU")
echo "$(date '+%F %T') Update $ALT → $NEU"

cd deploy
if echo "$GEAENDERT" | grep -qE '^(requirements\.txt|deploy/Dockerfile)$'; then
  docker compose up -d --build plattform
elif echo "$GEAENDERT" | grep -qE '^(runtime/|deploy/)'; then
  docker compose restart plattform
fi
