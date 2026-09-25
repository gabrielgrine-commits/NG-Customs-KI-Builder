#!/usr/bin/env python3
"""Richtet den Telefon-Assistenten eines Kunden direkt über die Vapi-API ein (ohne MCP).

  python scripts/vapi_einrichten.py --nummern                              # vorhandene Nummern anzeigen
  python scripts/vapi_einrichten.py kunden/<slug> rezeption                # Assistent anlegen/aktualisieren
  python scripts/vapi_einrichten.py kunden/<slug> rezeption --nummer <ID>  # … und Nummer verknüpfen
  python scripts/vapi_einrichten.py kunden/<slug> rezeption --trocken      # nur anzeigen, nichts senden
  python scripts/vapi_einrichten.py kunden/<slug> rezeption --ohne-plattform  # Übergang: ohne Werkzeuge

Braucht in der Umgebung: VAPI_TOKEN (Private Key), NGC_GEHEIMNIS und NGC_BASIS_URL (Plattform-Adresse,
unter der Vapi die Werkzeuge aufruft). Dieselben Funktionen gibt es in Claude Code als MCP-Server „vapi“
(scripts/vapi_mcp.py, Logik in runtime/vapi_api.py). Die Assistenten-ID wird in config.json unter
telefon.vapi_assistent_id gespeichert – beim nächsten Aufruf wird derselbe Assistent aktualisiert
statt ein neuer angelegt.

--ohne-plattform (solange der Server noch nicht läuft): Der Assistent beantwortet Fragen und nimmt
Anliegen im Gespräch auf, speichert aber nichts und benachrichtigt niemanden – die Gespräche stehen nur
in den Anrufprotokollen im Vapi-Dashboard. Sobald die Plattform läuft, ohne den Schalter erneut
ausführen: Derselbe Assistent bekommt dann Werkzeuge und Nachbearbeitung.

Hinweis: Kostenlose Vapi-Nummern gibt es nur für die USA. Deutsche Nummern (+49) werden bei Twilio,
Telnyx oder Vonage gekauft und im Vapi-Dashboard importiert; danach hier per --nummer verknüpfen.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runtime import vapi_api  # noqa: E402


def nummern_zeigen() -> list:
    liste = vapi_api.anfrage("GET", "/phone-number")
    if not liste:
        print("Keine Nummern im Vapi-Konto. Deutsche/österreichische Nummer: bei Twilio/Telnyx/Vonage kaufen und im "
              "Vapi-Dashboard importieren (Phone Numbers → Import).")
    for n in liste:
        print(f"{n.get('id')}  {n.get('number') or n.get('sipUri') or '?'}  "
              f"Anbieter: {n.get('provider', '?')}  Assistent: {n.get('assistantId') or '–'}")
    return liste


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kunde", nargs="?")
    p.add_argument("agent", nargs="?")
    p.add_argument("--nummer", help="Vapi-ID oder Rufnummer (+49…/+43…) einer importierten Nummer")
    p.add_argument("--nummern", action="store_true", help="Nummern im Vapi-Konto auflisten")
    p.add_argument("--trocken", action="store_true", help="Konfiguration nur anzeigen")
    p.add_argument("--ohne-plattform", action="store_true",
                   help="Übergang ohne Server: keine Werkzeuge, Gespräche nur im Vapi-Dashboard")
    args = p.parse_args()

    try:
        if args.nummern:
            nummern_zeigen()
            return
        if not (args.kunde and args.agent):
            p.error("kunde und agent angeben (oder --nummern)")
        if args.trocken:
            _, assistent = vapi_api.assistent_bauen(args.kunde, args.agent, ohne_plattform=args.ohne_plattform)
            print(json.dumps(vapi_api.vorschau(assistent), ensure_ascii=False, indent=2))
            return
        for meldung in vapi_api.einrichten(args.kunde, args.agent, args.nummer, args.ohne_plattform):
            print(meldung)
    except vapi_api.VapiFehler as e:
        sys.exit(f"❌ {e}")


if __name__ == "__main__":
    main()
