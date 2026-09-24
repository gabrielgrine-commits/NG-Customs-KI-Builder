#!/usr/bin/env python3
"""Fügt einem bestehenden Kunden einen Agententyp aus dem Katalog hinzu (oder entfernt ihn).

  python scripts/agent_hinzufuegen.py kunden/<slug> lead-nachfassen
  python scripts/agent_hinzufuegen.py kunden/<slug> lead-generierung --entfernen
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VORLAGEN = ROOT / "vorlagen"


def main() -> None:
    katalog = json.loads((VORLAGEN / "agenten" / "katalog.json").read_text(encoding="utf-8"))
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kunde")
    p.add_argument("typ", choices=sorted(katalog))
    p.add_argument("--entfernen", action="store_true")
    args = p.parse_args()

    agent_dir = Path(args.kunde) / "agent"
    cfg_pfad = agent_dir / "config.json"
    if not cfg_pfad.exists():
        sys.exit(f"{cfg_pfad} fehlt – zuerst scripts/neuer_kunde.py ausführen.")
    konfig = json.loads(cfg_pfad.read_text(encoding="utf-8"))
    eintrag = katalog[args.typ]

    if args.entfernen:
        if konfig["agenten"].pop(args.typ, None) is None:
            sys.exit(f"Agent '{args.typ}' ist nicht vorhanden.")
        print(f"➖ {args.typ} entfernt (Prompt-Datei agent/{eintrag['prompt']} bleibt liegen).")
    else:
        if args.typ in konfig["agenten"]:
            sys.exit(f"Agent '{args.typ}' ist schon vorhanden.")
        prompt_ziel = agent_dir / eintrag["prompt"]
        if not prompt_ziel.exists():
            text = (VORLAGEN / "agenten" / args.typ / "prompt.md").read_text(encoding="utf-8")
            text = text.replace("{{FIRMA}}", konfig["firma"]["name"]).replace(
                "{{ZIELPROFIL}}", "[OFFEN: Zielprofil aus der Analyse eintragen – Branche, Region, Größe, Bedarfssignale]")
            prompt_ziel.write_text(text, encoding="utf-8")
        konfig["agenten"][args.typ] = eintrag
        if "kalender" in eintrag["werkzeuge"] and "kalender" not in konfig:
            basis = json.loads((VORLAGEN / "config.basis.json").read_text(encoding="utf-8"))
            konfig["kalender"] = basis["kalender"]
        print(f"➕ {args.typ} hinzugefügt – Prompt agent/{eintrag['prompt']} an den Kunden anpassen.")

    cfg_pfad.write_text(json.dumps(konfig, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
