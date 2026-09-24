#!/bin/bash
# Installiert die Python-Abhängigkeiten, damit scripts/*.py und `python -m runtime` in
# Claude-Code-Web-Sitzungen sofort funktionieren (nur in der Cloud-Umgebung).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt 2>&1 | grep -v "Running pip as the 'root' user" || true
python3 -c "import anthropic" 
