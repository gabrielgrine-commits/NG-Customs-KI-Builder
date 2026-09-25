#!/usr/bin/env python3
"""Legt einen neuen Kundenordner mit Konfiguration, Agenten-Prompts und Fragebogen an.

  python scripts/neuer_kunde.py "Malerbetrieb Schmidt GmbH" --branche Handwerk \
      --agenten rezeption,lead-nachfassen
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VORLAGEN = ROOT / "vorlagen"


def slug(text: str) -> str:
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"\b(gmbh|ug|ag|kg|e\.?k\.?|ohg|gbr|co)\b", "", text)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def main() -> None:
    katalog = json.loads((VORLAGEN / "agenten" / "katalog.json").read_text(encoding="utf-8"))
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("firma")
    p.add_argument("--branche", required=True)
    p.add_argument("--agenten", default="rezeption",
                   help=f"Kommagetrennt aus: {', '.join(katalog)}")
    p.add_argument("--slug")
    p.add_argument("--land", choices=["DE", "AT"], default="DE", help="Rechtsrahmen und Zeitzone (Standard: DE)")
    args = p.parse_args()

    typen = [t.strip() for t in args.agenten.split(",") if t.strip()]
    unbekannt = [t for t in typen if t not in katalog]
    if unbekannt:
        sys.exit(f"Unbekannte Agententypen: {unbekannt}. Verfügbar: {', '.join(katalog)}")

    s = args.slug or slug(args.firma)
    ziel = ROOT / "kunden" / s
    if ziel.exists():
        sys.exit(f"{ziel} existiert bereits.")
    (ziel / "agent").mkdir(parents=True)

    env = re.sub(r"[^A-Z0-9]", "_", s.upper())
    ersetzen = {"{{FIRMA}}": args.firma, "{{BRANCHE}}": args.branche, "{{ENV}}": env,
                "{{ZIELPROFIL}}": "[OFFEN: Zielprofil aus der Analyse eintragen – Branche, Region, Größe, Bedarfssignale]"}

    def fuellen(text: str) -> str:
        for alt, neu in ersetzen.items():
            text = text.replace(alt, neu)
        return text

    konfig = json.loads(fuellen((VORLAGEN / "config.basis.json").read_text(encoding="utf-8")))
    konfig = {"land": args.land, **konfig}
    if args.land == "AT":
        konfig["zeitzone"] = "Europe/Vienna"
        konfig["telefon"]["stimme"]["voiceId"] = "de-AT-IngridNeural"  # österreichische Stimme
    for typ in typen:
        konfig["agenten"][typ] = katalog[typ]
        prompt = fuellen((VORLAGEN / "agenten" / typ / "prompt.md").read_text(encoding="utf-8"))
        (ziel / "agent" / katalog[typ]["prompt"]).write_text(prompt, encoding="utf-8")
    if not any("kalender" in katalog[t]["werkzeuge"] for t in typen):
        konfig.pop("kalender")

    (ziel / "agent" / "config.json").write_text(json.dumps(konfig, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ziel / "agent" / "wissen.md").write_text(fuellen((VORLAGEN / "wissen.vorlage.md").read_text(encoding="utf-8")),
                                              encoding="utf-8")
    (ziel / "00-intake.md").write_text(fuellen((VORLAGEN / "kunden-fragebogen.md").read_text(encoding="utf-8")),
                                       encoding="utf-8")

    print(f"✅ Kunde angelegt: kunden/{s}/")
    print(f"   Agenten: {', '.join(typen)}")
    print(f"   Nächster Schritt: Fragebogen kunden/{s}/00-intake.md ausfüllen, dann in Claude Code: /agent-bauen {s}")


if __name__ == "__main__":
    main()
