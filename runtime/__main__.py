"""Kommandozeile der Agenten-Laufzeit.

  python -m runtime pruefen      kunden/<slug>
  python -m runtime chat         kunden/<slug> <agent>
  python -m runtime nachricht    kunden/<slug> <agent> "Text" [--kanal email]
  python -m runtime auftrag      kunden/<slug> <agent> [--zusatz "..."]
  python -m runtime freigaben    kunden/<slug> [--alle]
  python -m runtime freigeben    kunden/<slug> <freigabe-id>
  python -m runtime ablehnen     kunden/<slug> <freigabe-id>
  python -m runtime leads        kunden/<slug>
  python -m runtime termine      kunden/<slug>
  python -m runtime berichte     kunden/<slug>
  python -m runtime server       kunden/<slug> [--port 8080]
  python -m runtime zeitplan     kunden/<slug>
  python -m runtime email        kunden/<slug> <agent> [--einmal]
"""

from __future__ import annotations

import argparse
import json
import sys

from . import config
from .engine import Agent, AgentFehler, freigabe_bearbeiten
from .store import JsonStore


def _drucke_aktionen(aktionen: list[dict]) -> None:
    for a in aktionen:
        erg = json.dumps(a["ergebnis"], ensure_ascii=False, default=str)
        print(f"  ⚙ {a['werkzeug']}({json.dumps(a['eingabe'], ensure_ascii=False)[:160]}) → {erg[:200]}")


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m runtime", description="NG Customs Agenten-Laufzeit")
    sub = p.add_subparsers(dest="befehl", required=True)
    for name in ("pruefen", "freigaben", "leads", "termine", "berichte", "server", "zeitplan"):
        s = sub.add_parser(name)
        s.add_argument("kunde")
        if name == "freigaben":
            s.add_argument("--alle", action="store_true")
        if name == "server":
            s.add_argument("--port", type=int, default=8080)
        if name == "zeitplan":
            s.add_argument("--jetzt", metavar="AGENT", help="Daueraufgabe dieses Agenten sofort einmal ausführen")
    for name in ("chat", "nachricht", "auftrag", "email"):
        s = sub.add_parser(name)
        s.add_argument("kunde")
        s.add_argument("agent")
        if name == "nachricht":
            s.add_argument("text")
            s.add_argument("--kanal", default="cli")
        if name == "auftrag":
            s.add_argument("--zusatz")
        if name == "email":
            s.add_argument("--einmal", action="store_true")
    for name in ("freigeben", "ablehnen"):
        s = sub.add_parser(name)
        s.add_argument("kunde")
        s.add_argument("id")
    args = p.parse_args()

    try:
        k = config.laden(args.kunde)
    except config.KonfigFehler as e:
        sys.exit(f"❌ {e}")
    store = JsonStore(k.daten_dir)

    try:
        if args.befehl == "pruefen":
            print(f"✅ Konfiguration von {k.firma['name']} ist gültig. Agenten:")
            for n, a in k.daten["agenten"].items():
                print(f"  • {n} ({a.get('typ', '?')}): Kanäle {a.get('kanaele', [])}, "
                      f"Werkzeuge {a.get('werkzeuge', [])}, Freigabe für {a.get('freigabe_erforderlich', [])}")

        elif args.befehl == "chat":
            agent = Agent(k, args.agent)
            print(f"Chat mit '{args.agent}' von {k.firma['name']} – leere Eingabe beendet.\n")
            verlauf: list = []
            while (eingabe := input("Sie: ").strip()):
                ergebnis, verlauf = agent.ausfuehren(eingabe, verlauf, kanal="chat")
                _drucke_aktionen(ergebnis.aktionen)
                print(f"\nAgent: {ergebnis.text}\n")

        elif args.befehl == "nachricht":
            ergebnis, _ = Agent(k, args.agent).ausfuehren(args.text, kanal=args.kanal)
            _drucke_aktionen(ergebnis.aktionen)
            print(ergebnis.text)

        elif args.befehl == "auftrag":
            ergebnis = Agent(k, args.agent).daueraufgabe(args.zusatz)
            _drucke_aktionen(ergebnis.aktionen)
            print(f"\n=== Bericht ===\n{ergebnis.text}")

        elif args.befehl == "freigaben":
            liste = [f for f in store.lesen("freigaben", []) if args.alle or f["status"] == "offen"]
            if not liste:
                print("Keine offenen Freigaben.")
            for f in liste:
                print(f"\n[{f['id']}] {f['status'].upper()} – {f['agent']} will {f['werkzeug']} ({f['erstellt_am']})")
                for feld, wert in f["eingabe"].items():
                    print(f"  {feld}: {wert}")

        elif args.befehl in ("freigeben", "ablehnen"):
            print(json.dumps(freigabe_bearbeiten(k, args.id, args.befehl == "freigeben"),
                             ensure_ascii=False, indent=2, default=str))

        elif args.befehl == "leads":
            for l in sorted(store.lesen("crm", []), key=lambda l: -l["bewertung"]):
                print(f"[{l['id']}] {l['bewertung']:>2}/10 {l['status']:<13} {l.get('firma') or l.get('name')} "
                      f"– {l.get('email') or l.get('telefon') or l.get('website')} | {l['anliegen'][:70]}"
                      + (f" | WV {l['naechster_schritt_am']}" if l.get("naechster_schritt_am") else ""))

        elif args.befehl == "termine":
            for t in sorted(store.lesen("termine", []), key=lambda t: t["start"]):
                print(f"[{t['id']}] {t['start']} ({t['dauer_min']} min) {t['status']:<10} {t['name']} – {t['anliegen'][:60]}")

        elif args.befehl == "berichte":
            for b in store.lesen("berichte", [])[-10:]:
                print(f"\n=== {b['zeit']} – {b['agent']} ({b['aktionen']} Aktionen) ===\n{b['bericht']}")

        elif args.befehl == "server":
            from .server import starten
            starten(k, port=args.port)

        elif args.befehl == "zeitplan":
            from .worker import zeitplan_schleife
            zeitplan_schleife(k, einmal_jetzt=args.jetzt)

        elif args.befehl == "email":
            from .worker import email_schleife
            email_schleife(k, args.agent, einmal=args.einmal)

    except config.KonfigFehler as e:
        sys.exit(f"❌ {e}")
    except AgentFehler as e:
        sys.exit(f"❌ Agent-Fehler: {e}")
    except (KeyboardInterrupt, EOFError):
        print()


if __name__ == "__main__":
    main()
