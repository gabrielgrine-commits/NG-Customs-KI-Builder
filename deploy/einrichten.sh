#!/usr/bin/env bash
# Einmalige Einrichtung der NG-Customs-Plattform auf einem frischen Ubuntu-Server (22.04/24.04),
# z. B. Hetzner Cloud CX22. Als root ausführen:
#
#   bash einrichten.sh
#
# Das Skript fragt nur nach: Repo-Adresse, Domain, Claude-API-Key. Alles andere passiert automatisch:
# Docker, Deploy-Key für GitHub, Geheimnis, HTTPS (Caddy), Autostart, Auto-Update alle 5 Minuten.
set -euo pipefail

frage() { local antwort; read -r -p "$1" antwort </dev/tty; echo "$antwort"; }

[ "$(id -u)" = 0 ] || { echo "Bitte als root ausführen (sudo bash einrichten.sh)"; exit 1; }
ZIEL=/opt/ng-customs

echo "== 1/6 Pakete & Docker"
apt-get update -qq
apt-get install -y -qq git curl openssl ca-certificates >/dev/null
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh >/dev/null
fi

echo "== 2/6 Zugriff auf das GitHub-Repository"
REPO=$(frage "GitHub-Repo (SSH, z. B. git@github.com:gabrielgrine-commits/NG-Customs-KI-Builder.git): ")
if [ ! -f /root/.ssh/ngc_deploy ]; then
  mkdir -p /root/.ssh && ssh-keygen -q -t ed25519 -N "" -f /root/.ssh/ngc_deploy -C "ngc-server"
  cat >>/root/.ssh/config <<EOF
Host github.com
  IdentityFile /root/.ssh/ngc_deploy
  StrictHostKeyChecking accept-new
EOF
fi
echo
echo "Diesen Schlüssel in GitHub eintragen: Repository → Settings → Deploy keys → Add deploy key"
echo "(Titel: Server, 'Allow write access' NICHT anhaken):"
echo
cat /root/.ssh/ngc_deploy.pub
echo
frage "Eingetragen? Dann Enter drücken … " >/dev/null

echo "== 3/6 Code holen"
if [ ! -d "$ZIEL/.git" ]; then
  git clone --quiet "$REPO" "$ZIEL"
fi
git config --global --add safe.directory "$ZIEL"
ZWEIG=$(frage "Welcher Branch soll live laufen? [main]: ")
ZWEIG=${ZWEIG:-main}
git -C "$ZIEL" checkout --quiet "$ZWEIG"

echo "== 4/6 Einstellungen"
ENV="$ZIEL/deploy/.env"
if [ ! -f "$ENV" ]; then
  DOMAIN=$(frage "Domain der Plattform (DNS muss auf diesen Server zeigen, z. B. agents.ng-customs.de): ")
  KEY=$(frage "Claude-API-Key (sk-ant-…): ")
  cat >"$ENV" <<EOF
DOMAIN=$DOMAIN
NGC_BASIS_URL=https://$DOMAIN
NGC_GEHEIMNIS=$(openssl rand -hex 32)
ANTHROPIC_API_KEY=$KEY
NGC_ZWEIG=$ZWEIG
EOF
  chmod 600 "$ENV"
fi
chown -R 1000:1000 "$ZIEL"   # Container läuft als Benutzer 1000 und schreibt kunden/*/daten/

echo "== 5/6 Start"
cd "$ZIEL/deploy" && docker compose up -d --build

echo "== 6/6 Auto-Update (alle 5 Minuten git pull)"
cat >/etc/cron.d/ngc-aktualisieren <<EOF
*/5 * * * * root NGC_ZWEIG=$ZWEIG bash $ZIEL/deploy/aktualisieren.sh >> /var/log/ngc-aktualisieren.log 2>&1
EOF

source "$ENV"
echo
echo "✅ Fertig. Plattform: https://$DOMAIN/gesundheit"
echo "   Demo eines Kunden:  https://$DOMAIN/k/<kunde>/demo"
echo
echo "WICHTIG – dieses Geheimnis auch in Claude Code als Umgebungsvariable NGC_GEHEIMNIS eintragen"
echo "(und NGC_BASIS_URL=https://$DOMAIN), damit Links und Tokens übereinstimmen:"
echo "   NGC_GEHEIMNIS=$NGC_GEHEIMNIS"
