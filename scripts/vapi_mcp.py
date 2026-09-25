#!/usr/bin/env python3
"""MCP-Server „vapi“ für Claude Code – verwaltet das Vapi-Konto von NG Customs (stdio, nur Standardbibliothek).

Eingetragen in .mcp.json; Claude Code startet ihn selbst. Werkzeuge:
  lesen:     vapi_status, vapi_nummern, vapi_assistenten, vapi_assistent, vapi_anrufe, vapi_anruf, vapi_vorschau
  schreiben: vapi_assistent_einrichten, vapi_nummer_verknuepfen, vapi_assistent_loeschen
             (nur nach ausdrücklicher Zustimmung des Nutzers – CLAUDE.md Regel 7)

Braucht VAPI_TOKEN (Private Key); zum Anlegen außerdem NGC_BASIS_URL und NGC_GEHEIMNIS.
Tokens werden in allen Ausgaben maskiert. Logik: runtime/vapi_api.py.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from runtime import vapi_api  # noqa: E402
from runtime.vapi_api import VapiFehler, anfrage, maskieren  # noqa: E402

KUNDEN = ROOT / "kunden"
SERVER_INFO = {"name": "ng-customs-vapi", "version": "1.0.0"}
HINWEIS = ("Vapi-Konto von NG Customs (Telefon-Assistenten der Kunden). Schreibende Werkzeuge "
           "(vapi_assistent_einrichten, vapi_nummer_verknuepfen, vapi_assistent_loeschen) nur nach ausdrücklicher "
           "Zustimmung des Nutzers verwenden – das betrifft echte Telefonnummern und kann Kosten verursachen.")


# ------------------------------------------------------------------ Hilfen

def _kunde(kunde: str) -> Path:
    """'ng-customs' oder 'kunden/ng-customs' → Kundenordner (nur innerhalb von kunden/)."""
    slug = kunde.strip().strip("/").removeprefix("kunden/")
    pfad = (KUNDEN / slug).resolve()
    if pfad.parent != KUNDEN.resolve() or not (pfad / "agent" / "config.json").is_file():
        vorhanden = sorted(p.name for p in KUNDEN.iterdir() if (p / "agent" / "config.json").is_file())
        raise VapiFehler(f"Kunde '{kunde}' nicht gefunden. Vorhanden: {', '.join(vorhanden)}")
    return pfad


def _zuordnung() -> dict[str, str]:
    """Vapi-Assistenten-ID → Kunde/Agent laut config.json (telefon.vapi_assistent_id)."""
    ergebnis = {}
    for cfg in KUNDEN.glob("*/agent/config.json"):
        try:
            roh = json.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for quelle, name in [(roh.get("telefon", {}), "")] + [(a.get("telefon", {}), f"/{n}")
                                                               for n, a in roh.get("agenten", {}).items()]:
            if quelle.get("vapi_assistent_id"):
                ergebnis[quelle["vapi_assistent_id"]] = cfg.parent.parent.name + name
    return ergebnis


def _dauer(anruf: dict) -> str:
    from datetime import datetime
    try:
        start = datetime.fromisoformat(anruf["startedAt"].replace("Z", "+00:00"))
        ende = datetime.fromisoformat(anruf["endedAt"].replace("Z", "+00:00"))
        return f"{int((ende - start).total_seconds())} s"
    except (KeyError, TypeError, ValueError):
        return "–"


# ------------------------------------------------------------------ Werkzeuge

def vapi_status(_: dict) -> Any:
    status = {"VAPI_TOKEN": bool(vapi_api.schluessel()),
              "NGC_BASIS_URL": os.environ.get("NGC_BASIS_URL", "") or "fehlt (nötig zum Anlegen)",
              "NGC_GEHEIMNIS": "gesetzt" if len(os.environ.get("NGC_GEHEIMNIS", "")) >= 16 else "fehlt (nötig zum Anlegen)"}
    try:
        status["assistenten"] = len(anfrage("GET", "/assistant", params={"limit": 100}))
        status["nummern"] = len(anfrage("GET", "/phone-number"))
        status["vapi"] = "verbunden"
    except VapiFehler as e:
        status["vapi"] = f"Fehler: {e}"
    return status


def vapi_nummern(_: dict) -> Any:
    liste = anfrage("GET", "/phone-number")
    if not liste:
        return ("Keine Nummern im Vapi-Konto. Österreichische/deutsche Nummern bei Twilio, Telnyx oder Vonage kaufen "
                "und im Vapi-Dashboard importieren (Phone Numbers → Import).")
    return [{"id": n.get("id"), "nummer": n.get("number") or n.get("sipUri"), "anbieter": n.get("provider"),
             "name": n.get("name"), "assistent_id": n.get("assistantId")} for n in liste]


def vapi_assistenten(args: dict) -> Any:
    zuordnung = _zuordnung()
    liste = anfrage("GET", "/assistant", params={"limit": args.get("limit") or 100})
    return [{"id": a.get("id"), "name": a.get("name"), "kunde": zuordnung.get(a.get("id"), "–"),
             "modell": (a.get("model") or {}).get("model"), "stimme": (a.get("voice") or {}).get("voiceId"),
             "geaendert": a.get("updatedAt")} for a in liste] or "Keine Assistenten im Vapi-Konto."


def vapi_assistent(args: dict) -> Any:
    a = maskieren(anfrage("GET", f"/assistant/{args['assistent_id']}"))
    if not args.get("voll"):
        for m in (a.get("model") or {}).get("messages", []):
            if len(m.get("content", "")) > 500:
                m["content"] = m["content"][:500] + f" … ({len(m['content'])} Zeichen, voll=true für alles)"
    return a


def vapi_anrufe(args: dict) -> Any:
    liste = anfrage("GET", "/call", params={"assistantId": args.get("assistent_id"), "limit": args.get("limit") or 10})
    return [{"id": c.get("id"), "start": c.get("startedAt") or c.get("createdAt"), "dauer": _dauer(c),
             "status": c.get("status"), "ende": c.get("endedReason"),
             "anrufer": (c.get("customer") or {}).get("number"), "assistent_id": c.get("assistantId"),
             "kosten_usd": c.get("cost")} for c in liste] or "Keine Anrufe gefunden."


def vapi_anruf(args: dict) -> Any:
    c = anfrage("GET", f"/call/{args['anruf_id']}")
    artefakt = c.get("artifact") or {}
    return {"id": c.get("id"), "start": c.get("startedAt"), "dauer": _dauer(c), "status": c.get("status"),
            "ende": c.get("endedReason"), "anrufer": (c.get("customer") or {}).get("number"),
            "assistent_id": c.get("assistantId"), "kosten_usd": c.get("cost"),
            "zusammenfassung": (c.get("analysis") or {}).get("summary"),
            "transkript": artefakt.get("transcript") or c.get("transcript"),
            "aufnahme": artefakt.get("recordingUrl") or "keine (Audioaufnahme ist ausgeschaltet)"}


def vapi_vorschau(args: dict) -> Any:
    _, assistent = vapi_api.assistent_bauen(_kunde(args["kunde"]), args["agent"], platzhalter=True,
                                            ohne_plattform=bool(args.get("ohne_plattform")))
    v = vapi_api.vorschau(assistent, prompt_zeichen=args.get("prompt_zeichen") or 300)
    if vapi_api.PLATZHALTER_URL in v.get("server", {}).get("url", ""):
        v["hinweis"] = "NGC_BASIS_URL/NGC_GEHEIMNIS fehlen – Adresse ist ein Platzhalter; Anlegen geht so noch nicht."
    return v


def vapi_assistent_einrichten(args: dict) -> Any:
    return vapi_api.einrichten(_kunde(args["kunde"]), args["agent"], args.get("nummer"),
                               bool(args.get("ohne_plattform")))


def vapi_nummer_verknuepfen(args: dict) -> Any:
    treffer = vapi_api.nummer_finden(args["nummer"])
    anfrage("PATCH", f"/phone-number/{treffer['id']}", {"assistantId": args.get("assistent_id") or None})
    if args.get("assistent_id"):
        return f"📞 {treffer.get('number')} ist jetzt mit Assistent {args['assistent_id']} verbunden."
    return f"📞 {treffer.get('number')} ist jetzt mit keinem Assistenten mehr verbunden."


def vapi_assistent_loeschen(args: dict) -> Any:
    aid = args["assistent_id"]
    geloescht = anfrage("DELETE", f"/assistant/{aid}")
    meldungen = [f"🗑️ Assistent gelöscht: {aid} ({geloescht.get('name')})"]
    for cfg in KUNDEN.glob("*/agent/config.json"):  # veraltete ID aus config.json entfernen
        roh = json.loads(cfg.read_text(encoding="utf-8"))
        bereiche = [roh.get("telefon", {})] + [a.get("telefon", {}) for a in roh.get("agenten", {}).values()]
        if any(b.get("vapi_assistent_id") == aid for b in bereiche):
            for b in bereiche:
                if b.get("vapi_assistent_id") == aid:
                    b.pop("vapi_assistent_id")
            cfg.write_text(json.dumps(roh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            meldungen.append(f"ID aus {cfg.relative_to(ROOT)} entfernt.")
    return meldungen


KUNDE_AGENT = {"kunde": {"type": "string", "description": "Kunden-Slug, z. B. 'ng-customs'"},
               "agent": {"type": "string", "description": "Agent mit Kanal 'telefon', z. B. 'rezeption'"},
               "ohne_plattform": {"type": "boolean", "description": "Übergang, solange der Server nicht läuft: "
                                  "keine Werkzeuge, Gespräche nur im Vapi-Dashboard"}}
LESEN = {"readOnlyHint": True, "openWorldHint": True}

WERKZEUGE: dict[str, tuple[Callable[[dict], Any], str, dict, list[str], dict]] = {
    "vapi_status": (vapi_status, "Prüft Verbindung und Umgebung: VAPI_TOKEN, NGC_BASIS_URL, NGC_GEHEIMNIS, "
                    "Anzahl Assistenten und Nummern.", {}, [], LESEN),
    "vapi_nummern": (vapi_nummern, "Listet die Telefonnummern im Vapi-Konto (ID, Nummer, Anbieter, verknüpfter "
                     "Assistent).", {}, [], LESEN),
    "vapi_assistenten": (vapi_assistenten, "Listet die Assistenten im Vapi-Konto mit Zuordnung zum Kunden laut "
                         "config.json.", {"limit": {"type": "integer", "description": "Höchstens so viele (Standard 100)"}},
                         [], LESEN),
    "vapi_assistent": (vapi_assistent, "Zeigt die Konfiguration eines Assistenten (Tokens maskiert).",
                       {"assistent_id": {"type": "string"},
                        "voll": {"type": "boolean", "description": "Systemprompt vollständig statt gekürzt"}},
                       ["assistent_id"], LESEN),
    "vapi_anrufe": (vapi_anrufe, "Listet die letzten Anrufe (optional nur eines Assistenten) mit Dauer, "
                    "Ende-Grund, Anrufernummer und Kosten.",
                    {"assistent_id": {"type": "string"}, "limit": {"type": "integer", "description": "Standard 10"}},
                    [], LESEN),
    "vapi_anruf": (vapi_anruf, "Zeigt einen Anruf mit Transkript und Zusammenfassung (personenbezogene Daten – "
                   "nur für die Bearbeitung verwenden).", {"anruf_id": {"type": "string"}}, ["anruf_id"], LESEN),
    "vapi_vorschau": (vapi_vorschau, "Vorschau der Assistenten-Konfiguration aus kunden/<slug>/agent (sendet nichts "
                      "an Vapi; ohne NGC_BASIS_URL mit Platzhalter-Adresse).",
                      {**KUNDE_AGENT, "prompt_zeichen": {"type": "integer", "description": "Prompt-Länge in der "
                                                         "Vorschau (Standard 300)"}},
                      ["kunde", "agent"], {"readOnlyHint": True, "openWorldHint": False}),
    "vapi_assistent_einrichten": (vapi_assistent_einrichten, "Legt den Telefon-Assistenten eines Kunden bei Vapi an "
                                  "oder aktualisiert ihn (telefon.vapi_assistent_id in config.json) und verknüpft "
                                  "optional eine Nummer. NUR nach ausdrücklicher Zustimmung des Nutzers.",
                                  {**KUNDE_AGENT, "nummer": {"type": "string", "description": "Vapi-Nummern-ID oder "
                                                             "Rufnummer (+43…/+49…), optional"}},
                                  ["kunde", "agent"],
                                  {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True}),
    "vapi_nummer_verknuepfen": (vapi_nummer_verknuepfen, "Verbindet eine Nummer mit einem Assistenten (ohne "
                                "assistent_id: Verbindung lösen). NUR nach ausdrücklicher Zustimmung des Nutzers.",
                                {"nummer": {"type": "string", "description": "Vapi-Nummern-ID oder Rufnummer"},
                                 "assistent_id": {"type": "string"}},
                                ["nummer"], {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True}),
    "vapi_assistent_loeschen": (vapi_assistent_loeschen, "Löscht einen Assistenten bei Vapi und entfernt seine ID aus "
                                "config.json. NUR nach ausdrücklicher Zustimmung des Nutzers.",
                                {"assistent_id": {"type": "string"}}, ["assistent_id"],
                                {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False}),
}


def werkzeug_liste() -> list[dict]:
    return [{"name": name, "description": beschreibung,
             "inputSchema": {"type": "object", "properties": props, "required": pflicht},
             "annotations": hinweise}
            for name, (_, beschreibung, props, pflicht, hinweise) in WERKZEUGE.items()]


def werkzeug_aufrufen(name: str, args: dict) -> dict:
    if name not in WERKZEUGE:
        return {"content": [{"type": "text", "text": f"Unbekanntes Werkzeug: {name}"}], "isError": True}
    funktion, _, _, pflicht, _ = WERKZEUGE[name]
    fehlend = [f for f in pflicht if not args.get(f)]
    try:
        if fehlend:
            raise VapiFehler(f"Pflichtangaben fehlen: {', '.join(fehlend)}")
        ergebnis = funktion(args)
        text = ergebnis if isinstance(ergebnis, str) else json.dumps(ergebnis, ensure_ascii=False, indent=2)
        return {"content": [{"type": "text", "text": text}], "isError": False}
    except VapiFehler as e:
        return {"content": [{"type": "text", "text": f"❌ {e}"}], "isError": True}
    except Exception as e:  # Server darf nie abstürzen
        return {"content": [{"type": "text", "text": f"❌ {type(e).__name__}: {e}"}], "isError": True}


# ------------------------------------------------------------------ JSON-RPC über stdio

def bearbeiten(nachricht: dict) -> dict | None:
    methode, mid = nachricht.get("method"), nachricht.get("id")
    if mid is None:  # Benachrichtigung (z. B. notifications/initialized) – keine Antwort
        return None
    params = nachricht.get("params") or {}
    if methode == "initialize":
        ergebnis = {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER_INFO, "instructions": HINWEIS}
    elif methode == "ping":
        ergebnis = {}
    elif methode == "tools/list":
        ergebnis = {"tools": werkzeug_liste()}
    elif methode == "tools/call":
        ergebnis = werkzeug_aufrufen(params.get("name", ""), params.get("arguments") or {})
    elif methode in ("resources/list", "prompts/list"):
        ergebnis = {methode.split("/")[0]: []}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Methode unbekannt: {methode}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": ergebnis}


def main() -> None:
    for zeile in sys.stdin:
        if not zeile.strip():
            continue
        try:
            nachricht = json.loads(zeile)
        except json.JSONDecodeError:
            antwort: Any = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Ungültiges JSON"}}
        else:
            if isinstance(nachricht, list):
                antwort = [a for a in (bearbeiten(n) for n in nachricht) if a] or None
            else:
                antwort = bearbeiten(nachricht)
        if antwort:
            sys.stdout.write(json.dumps(antwort, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
