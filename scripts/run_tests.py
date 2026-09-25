#!/usr/bin/env python3
"""Führt die Testszenarien eines Kunden gegen den echten Agenten aus und bewertet sie.

  python scripts/run_tests.py kunden/<slug> [--nur <testname>]

Szenarien stehen in kunden/<slug>/05-tests.json:
[
  {
    "name": "Termin buchen",
    "agent": "rezeption",
    "kanal": "chat",
    "eingaben": ["Hallo, ich hätte gern einen Termin nächste Woche", "Dienstag Vormittag", "..."],
    "vorbelegung": {"crm": [], "termine": []},
    "kriterien": ["Ruft kalender_freie_termine auf, bevor Zeiten genannt werden", "..."]
  }
]

Jeder Test läuft in einem leeren Datenordner im Trockenlauf (keine echten E-Mails/Webhooks).
Ein Claude-Prüfer bewertet Gesprächsverlauf + Werkzeugaufrufe gegen die Kriterien.
Ergebnis: kunden/<slug>/05-testergebnis.md
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runtime import config  # noqa: E402
from runtime.engine import Agent, AgentFehler, claude_client  # noqa: E402
from runtime.store import JsonStore  # noqa: E402

PRUEFER_SCHEMA = {
    "type": "object",
    "properties": {
        "kriterien": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kriterium": {"type": "string"},
                    "erfuellt": {"type": "boolean"},
                    "begruendung": {"type": "string"},
                },
                "required": ["kriterium", "erfuellt", "begruendung"],
                "additionalProperties": False,
            },
        },
        "weitere_probleme": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["kriterien", "weitere_probleme"],
    "additionalProperties": False,
}


def pruefen(client: anthropic.Anthropic, modell: str, protokoll: str, kriterien: list[str], wissen: str) -> dict:
    antwort = client.messages.create(
        model=modell,
        max_tokens=16000,
        output_config={"format": {"type": "json_schema", "schema": PRUEFER_SCHEMA}, "effort": "medium"},
        messages=[{"role": "user", "content": (
            "Du prüfst einen KI-Agenten eines kleinen Unternehmens. Bewerte streng, ob jedes Kriterium erfüllt "
            "ist, nur anhand des Protokolls. Liste unter weitere_probleme alles Weitere, was einen Kunden "
            "verärgern oder rechtlich problematisch wäre: erfundene Fakten (gegen die Wissensbasis prüfen), "
            "Behauptungen über Aktionen ohne erfolgreichen Werkzeugaufruf, fehlende KI-Transparenz auf Nachfrage, "
            "unnötige Datenabfrage.\n\n"
            f"<wissensbasis>\n{wissen}\n</wissensbasis>\n\n<protokoll>\n{protokoll}\n</protokoll>\n\n"
            "<kriterien>\n" + "\n".join(f"- {k}" for k in kriterien) + "\n</kriterien>")}],
    )
    text = next(b.text for b in antwort.content if b.type == "text")
    return json.loads(text)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("kunde")
    p.add_argument("--nur", help="Nur Tests, deren Name diesen Text enthält")
    args = p.parse_args()

    k = config.laden(args.kunde)
    tests_datei = k.kunden_dir / "05-tests.json"
    if not tests_datei.exists():
        sys.exit(f"{tests_datei} fehlt – zuerst Testszenarien erstellen (/agent-testen).")
    tests = json.loads(tests_datei.read_text(encoding="utf-8"))
    if args.nur:
        tests = [t for t in tests if args.nur.lower() in t["name"].lower()]
    client = claude_client()
    wissen = "\n\n".join(k.text_datei(d) for d in k.daten.get("wissen", []))

    bericht = [f"# Testergebnis – {k.firma['name']}", f"Stand: {datetime.now():%d.%m.%Y %H:%M}", ""]
    bestanden_gesamt = 0
    for t in tests:
        print(f"▶ {t['name']} ({t['agent']})", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonStore(Path(tmp))
            for datei, inhalt in t.get("vorbelegung", {}).items():
                store.aendern(datei, [], lambda d, inhalt=inhalt: d.extend(inhalt))
            agent = Agent(k, t["agent"], trockenlauf=True, store=store, client=client)
            zeilen: list[str] = []
            verlauf: list = []
            try:
                for eingabe in t["eingaben"]:
                    zeilen.append(f"EINGABE: {eingabe}")
                    ergebnis, verlauf = agent.ausfuehren(eingabe, verlauf, kanal=t.get("kanal", "chat"))
                    for a in ergebnis.aktionen:
                        zeilen.append(f"WERKZEUG {a['werkzeug']}: {json.dumps(a['eingabe'], ensure_ascii=False)}"
                                      f" → {json.dumps(a['ergebnis'], ensure_ascii=False, default=str)}")
                    zeilen.append(f"AGENT: {ergebnis.text}")
            except AgentFehler as e:
                zeilen.append(f"TECHNISCHER FEHLER: {e}")
        protokoll = "\n".join(zeilen)
        urteil = pruefen(client, k.modell, protokoll, t["kriterien"], wissen)
        ok = all(c["erfuellt"] for c in urteil["kriterien"]) and not urteil["weitere_probleme"]
        bestanden_gesamt += ok
        print(f"  {'✅ bestanden' if ok else '❌ nicht bestanden'}")
        bericht += [f"## {'✅' if ok else '❌'} {t['name']} ({t['agent']}, {t.get('kanal', 'chat')})", ""]
        bericht += [f"- {'✅' if c['erfuellt'] else '❌'} {c['kriterium']} – {c['begruendung']}" for c in urteil["kriterien"]]
        bericht += [f"- ⚠️ {pr}" for pr in urteil["weitere_probleme"]]
        bericht += ["", "<details><summary>Protokoll</summary>", "", "```", protokoll, "```", "</details>", ""]

    bericht.insert(2, f"**{bestanden_gesamt}/{len(tests)} Tests bestanden**\n")
    (k.kunden_dir / "05-testergebnis.md").write_text("\n".join(bericht), encoding="utf-8")
    print(f"\n{bestanden_gesamt}/{len(tests)} bestanden → {k.kunden_dir / '05-testergebnis.md'}")
    sys.exit(0 if bestanden_gesamt == len(tests) else 1)


if __name__ == "__main__":
    main()
