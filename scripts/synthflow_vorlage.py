#!/usr/bin/env python3
"""Erzeugt den Bauplan für einen Synthflow-Telefonagenten aus der Kunden-Konfiguration.

  python scripts/synthflow_vorlage.py kunden/<slug> rezeption

Schreibt kunden/<slug>/agent/synthflow.json mit:
  - prompt, begruessung, sprache
  - custom_actions: je Werkzeug ein HTTP-Aufruf an unsere Plattform (POST …/synthflow/<agent>/<werkzeug>)
    inkl. Body-Vorlage mit <variablen> und deren Beschreibung
  - post_call_webhook: …/synthflow/<agent>/nach-anruf (Transkript → Nachbearbeitung durch unseren Agenten)

Mit verbundenem Synthflow-Connector legt Claude daraus Agent + Custom Actions an (Regel: nur nach
Zustimmung des Nutzers). Die Datei enthält den API-Token im Klartext → in .gitignore.
Braucht NGC_BASIS_URL und NGC_GEHEIMNIS (für eine Vorschau ohne Server: --vorschau).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runtime import config  # noqa: E402
from runtime.geheimnisse import kunden_url, token  # noqa: E402
from runtime.telefon import _fuer_vapi, assistent_konfig  # noqa: E402
from runtime.werkzeuge import TOOL_DEFINITIONEN  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kunde")
    p.add_argument("agent")
    p.add_argument("--vorschau", action="store_true", help="Platzhalter statt echter URL/Token, nur anzeigen")
    args = p.parse_args()

    try:
        k = config.laden(args.kunde)
    except config.KonfigFehler as e:
        sys.exit(f"❌ {e}")
    if "telefon" not in k.agent(args.agent).get("kanaele", []):
        sys.exit(f"❌ Agent '{args.agent}' hat den Kanal 'telefon' nicht in config.json.")
    basis, api_token = kunden_url(k), token(k, "api")
    if args.vorschau:
        basis, api_token = basis or "https://agents.BEISPIEL.at/k/" + k.kunden_dir.name, "***"
    elif not basis.startswith("https://") or len(api_token) < 16:
        sys.exit("❌ NGC_BASIS_URL (https://…) und NGC_GEHEIMNIS setzen – oder --vorschau für einen Entwurf.")

    vapi = assistent_konfig(k, args.agent, basis, api_token)  # gleicher Prompt/gleiche Werkzeuge wie bei Vapi
    aktionen = []
    for tool in vapi["model"]["tools"]:
        name = tool["function"]["name"]
        schema = _fuer_vapi(TOOL_DEFINITIONEN[name])
        aktionen.append({
            "name": name,
            "beschreibung": TOOL_DEFINITIONEN[name]["description"],
            "methode": "POST",
            "url": f"{basis}/synthflow/{args.agent}/{name}",
            "headers": {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
            "body": {feld: f"<{feld}>" for feld in schema["properties"]},
            "variablen": {feld: {"beschreibung": d.get("description", ""), "pflicht": feld in schema["required"]}
                          for feld, d in schema["properties"].items()},
            "antwort": "JSON: ergebnis (Objekt) und ergebnis_text (Kurzfassung für den Agenten)",
        })

    bauplan = {
        "name": vapi["name"],
        "sprache": "de",
        "region": "EU (mcp.eu.synthflow.ai)",
        "begruessung": vapi["firstMessage"],
        "verabschiedung": vapi["endCallMessage"],
        "prompt": vapi["model"]["messages"][0]["content"].replace(
            "{{\"now\" | date: \"%A, %d.%m.%Y %H:%M\", \"" + k.zeitzone + "\"}}",
            "<aktuelles Datum und Uhrzeit – Synthflow-Aktion „Retrieve Date and Time“ nutzen>"),
        "custom_actions": aktionen,
        "post_call_webhook": {"url": f"{basis}/synthflow/{args.agent}/nach-anruf",
                              "headers": {"Authorization": f"Bearer {api_token}"}},
        "hinweise": [
            "Österreich/Deutschland: Nummern nicht direkt bei Synthflow kaufbar – z. B. Twilio-Nummer per SIP "
            "importieren (Custom Phone Numbers).",
            "Die Plattform muss unter der URL öffentlich per HTTPS erreichbar sein, sonst laufen die Aktionen ins Leere.",
        ],
    }
    if args.vorschau:
        print(json.dumps({**bauplan, "prompt": bauplan["prompt"][:400] + " …"}, ensure_ascii=False, indent=2))
        return
    ziel = k.agent_dir / "synthflow.json"
    ziel.write_text(json.dumps(bauplan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ {ziel} geschrieben – {len(aktionen)} Custom Actions: {', '.join(a['name'] for a in aktionen)}")


if __name__ == "__main__":
    main()
