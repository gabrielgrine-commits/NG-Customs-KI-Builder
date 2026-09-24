#!/usr/bin/env python3
"""Richtet den Telefon-Assistenten eines Kunden direkt über die Vapi-API ein (ohne MCP).

  python scripts/vapi_einrichten.py --nummern                              # vorhandene Nummern anzeigen
  python scripts/vapi_einrichten.py kunden/<slug> rezeption                # Assistent anlegen/aktualisieren
  python scripts/vapi_einrichten.py kunden/<slug> rezeption --nummer <ID>  # … und Nummer verknüpfen
  python scripts/vapi_einrichten.py kunden/<slug> rezeption --trocken      # nur anzeigen, nichts senden

Braucht in der Umgebung: VAPI_TOKEN (Private Key), NGC_GEHEIMNIS und NGC_BASIS_URL (Plattform-Adresse,
unter der Vapi die Werkzeuge aufruft). Die Assistenten-ID wird in config.json unter
telefon.vapi_assistent_id gespeichert – beim nächsten Aufruf wird derselbe Assistent aktualisiert
statt ein neuer angelegt.

Hinweis: Kostenlose Vapi-Nummern gibt es nur für die USA. Deutsche Nummern (+49) werden bei Twilio,
Telnyx oder Vonage gekauft und im Vapi-Dashboard importiert; danach hier per --nummer verknüpfen.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runtime import config  # noqa: E402
from runtime.geheimnisse import kunden_url, token  # noqa: E402
from runtime.telefon import assistent_konfig  # noqa: E402

API = "https://api.vapi.ai"


def vapi(methode: str, pfad: str, daten: dict | None = None) -> dict | list:
    schluessel = os.environ.get("VAPI_TOKEN", "")
    if not schluessel:
        sys.exit("❌ VAPI_TOKEN fehlt: Private Key aus dem Vapi-Dashboard als Umgebungsvariable setzen "
                 "(nicht in den Chat schreiben).")
    req = urllib.request.Request(
        API + pfad, method=methode,
        data=json.dumps(daten).encode() if daten is not None else None,
        headers={"Authorization": f"Bearer {schluessel}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as antwort:
            return json.loads(antwort.read() or b"{}")
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")[:1000]
        sys.exit(f"❌ Vapi {methode} {pfad}: HTTP {e.code} – {text}")
    except urllib.error.URLError as e:
        sys.exit(f"❌ Vapi nicht erreichbar: {e.reason}")


def nummern_zeigen() -> list:
    liste = vapi("GET", "/phone-number")
    if not liste:
        print("Keine Nummern im Vapi-Konto. Deutsche Nummer: bei Twilio/Telnyx/Vonage kaufen und im "
              "Vapi-Dashboard importieren (Phone Numbers → Import).")
    for n in liste:
        print(f"{n.get('id')}  {n.get('number') or n.get('sipUri') or '?'}  "
              f"Anbieter: {n.get('provider', '?')}  Assistent: {n.get('assistantId') or '–'}")
    return liste


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kunde", nargs="?")
    p.add_argument("agent", nargs="?")
    p.add_argument("--nummer", help="Vapi-ID oder Rufnummer (+49…) einer importierten Nummer")
    p.add_argument("--nummern", action="store_true", help="Nummern im Vapi-Konto auflisten")
    p.add_argument("--trocken", action="store_true", help="Konfiguration nur anzeigen")
    args = p.parse_args()

    if args.nummern:
        nummern_zeigen()
        return
    if not (args.kunde and args.agent):
        p.error("kunde und agent angeben (oder --nummern)")

    try:
        k = config.laden(args.kunde)
    except config.KonfigFehler as e:
        sys.exit(f"❌ {e}")
    if "telefon" not in k.agent(args.agent).get("kanaele", []):
        sys.exit(f"❌ Agent '{args.agent}' hat den Kanal 'telefon' nicht in config.json.")
    server_url, api_token = kunden_url(k), token(k, "api")
    if not server_url.startswith("https://") or len(api_token) < 16:
        sys.exit("❌ NGC_BASIS_URL (https://…) und NGC_GEHEIMNIS müssen gesetzt sein – Vapi braucht die "
                 "öffentliche Plattform-Adresse, um Termine zu buchen und Leads zu speichern.")

    assistent = assistent_konfig(k, args.agent, server_url, api_token)
    if args.trocken:
        vorschau = json.loads(json.dumps(assistent))
        for t in vorschau["model"]["tools"] + [vorschau]:
            t.get("server", {}).get("headers", {}).update(Authorization="Bearer ***")
        vorschau["model"]["messages"][0]["content"] = vorschau["model"]["messages"][0]["content"][:300] + " …"
        print(json.dumps(vorschau, ensure_ascii=False, indent=2))
        return

    cfg_pfad = k.agent_dir / "config.json"
    roh = json.loads(cfg_pfad.read_text(encoding="utf-8"))
    tel = roh.setdefault("telefon", {})
    vorhandene_id = tel.get("vapi_assistent_id")
    if vorhandene_id:
        ergebnis = vapi("PATCH", f"/assistant/{vorhandene_id}", assistent)
        print(f"🔄 Assistent aktualisiert: {ergebnis.get('id')}")
    else:
        ergebnis = vapi("POST", "/assistant", assistent)
        tel["vapi_assistent_id"] = ergebnis["id"]
        print(f"✅ Assistent angelegt: {ergebnis['id']}")

    if args.nummer:
        nummern = vapi("GET", "/phone-number")
        treffer = next((n for n in nummern if args.nummer in (n.get("id"), n.get("number"))), None)
        if not treffer:
            sys.exit(f"❌ Nummer {args.nummer} nicht im Vapi-Konto. Vorhanden:\n" +
                     "\n".join(f"  {n.get('id')} {n.get('number')}" for n in nummern))
        vapi("PATCH", f"/phone-number/{treffer['id']}", {"assistantId": tel["vapi_assistent_id"]})
        tel["nummer"] = treffer.get("number")
        tel["vapi_nummer_id"] = treffer["id"]
        print(f"📞 {treffer.get('number')} ist jetzt mit dem Assistenten verbunden.")

    cfg_pfad.write_text(json.dumps(roh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"   Gespeichert in {cfg_pfad} (telefon.vapi_assistent_id{', nummer' if args.nummer else ''}).")


if __name__ == "__main__":
    main()
