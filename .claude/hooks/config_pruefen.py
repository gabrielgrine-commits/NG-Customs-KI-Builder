#!/usr/bin/env python3
"""PostToolUse-Hook: prüft kunden/*/agent/config.json nach jeder Änderung.

Bei ungültiger Konfiguration Exit-Code 2 → Claude Code zeigt Claude die Fehlermeldung und es
korrigiert die Datei sofort.
"""

import json
import subprocess
import sys
from pathlib import Path

daten = json.load(sys.stdin)
pfad = Path(daten.get("tool_input", {}).get("file_path", ""))
teile = pfad.parts
if "kunden" in teile and "agent" in teile and pfad.suffix in (".json", ".md"):
    kunden_dir = Path(*teile[: teile.index("agent")])
    if (kunden_dir / "agent" / "config.json").exists():
        root = Path(__file__).resolve().parents[2]
        r = subprocess.run([sys.executable, str(root / "scripts" / "validate_config.py"), str(kunden_dir)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr or r.stdout, file=sys.stderr)
            sys.exit(2)
sys.exit(0)
