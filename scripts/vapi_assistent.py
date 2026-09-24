#!/usr/bin/env python3
"""Erzeugt die Vapi-Assistenten-Konfiguration (Telefon-Agent) für einen Kunden-Agenten.

  python scripts/vapi_assistent.py kunden/<slug> rezeption            # Plattform (NGC_BASIS_URL gesetzt)
  python scripts/vapi_assistent.py kunden/<slug> rezeption --server-url https://agent.kunde.de   # Einzelserver

Schreibt kunden/<slug>/agent/vapi-assistent.json. Diese Datei wird dann
  - in Claude Code über das Vapi-MCP (Werkzeug zum Anlegen/Aktualisieren eines Assistenten) übertragen, oder
  - per Vapi-API/Dashboard angelegt.
Danach im Vapi-Dashboard eine Telefonnummer mit dem Assistenten verknüpfen.

Der Token für /vapi/<agent> wird aus NGC_GEHEIMNIS abgeleitet (oder aus server.token_env) und steht
danach im Klartext in der JSON-Datei – deshalb ist vapi-assistent.json in .gitignore.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runtime import config  # noqa: E402
from runtime.geheimnisse import kunden_url, token  # noqa: E402
from runtime.telefon import assistent_konfig  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kunde")
    p.add_argument("agent")
    p.add_argument("--server-url", help="Nur Einzelserver: öffentliche HTTPS-Adresse von 'python -m runtime server'. "
                                        "Standard: NGC_BASIS_URL/k/<slug>")
    args = p.parse_args()

    try:
        k = config.laden(args.kunde)
    except config.KonfigFehler as e:
        sys.exit(f"❌ {e}")
    if "telefon" not in k.agent(args.agent).get("kanaele", []):
        sys.exit(f"❌ Agent '{args.agent}' hat den Kanal 'telefon' nicht in config.json.")
    server_url = args.server_url or kunden_url(k)
    if not server_url.startswith("https://"):
        sys.exit("❌ Server-Adresse fehlt oder ist nicht https:// – NGC_BASIS_URL setzen oder --server-url angeben.")
    api_token = token(k, "api")
    if len(api_token) < 16:
        sys.exit("❌ Kein Token: NGC_GEHEIMNIS (mind. 16 Zeichen, z. B. `openssl rand -hex 24`) setzen – "
                 "derselbe Wert wie auf dem Server.")

    assistent = assistent_konfig(k, args.agent, server_url, api_token)
    ziel = k.agent_dir / "vapi-assistent.json"
    ziel.write_text(json.dumps(assistent, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ {ziel} geschrieben")
    print(f"   Werkzeuge: {', '.join(t['function']['name'] for t in assistent['model']['tools'])}")
    print(f"   Modell: {assistent['model']['model']} · Stimme: {assistent['voice']} · Sprache: {assistent['transcriber']}")
    print("   Nächster Schritt: Assistent über das Vapi-MCP anlegen und eine Telefonnummer zuweisen.")


if __name__ == "__main__":
    main()
