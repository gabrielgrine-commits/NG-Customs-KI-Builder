"""Telefon-Kanal über Vapi (https://vapi.ai).

Aufgabenteilung:
  - Vapi: Telefonnummer, Spracherkennung, Sprachausgabe und das Gespräch selbst (LLM bei Vapi).
  - Diese Plattform: Werkzeuge (Kalender, CRM, Team …) über POST /vapi/<agent>, dieselben
    Freigaberegeln und dasselbe Audit-Protokoll wie bei Chat/E-Mail, und die Nachbearbeitung jedes
    Anrufs durch unseren Agenten (Transkript → Lead/Team prüfen und ergänzen).

Die Assistenten-Konfiguration für Vapi erzeugt scripts/vapi_assistent.py aus config.json,
Agenten-Prompt und Wissensbasis.
"""

from __future__ import annotations

import copy
import json
import re
import threading
from typing import Any

from .config import KundenKonfig
from .engine import PLATTFORM_REGELN, Agent, _firma_block, _rechtsrahmen
from .werkzeuge import SERVER_WERKZEUGE, TOOL_DEFINITIONEN

# Vapi bietet nur ausgewählte Anthropic-Modelle an (claude-opus-5 z. B. nicht) – deshalb eigener Standard
# statt konfig.modell. Liste: https://api.vapi.ai/api-json → AnthropicModel.model
VAPI_MODELL = "claude-sonnet-5"
VAPI_NAME_MAX = 40  # Vapi lehnt längere Assistenten-Namen ab
RECHTSFORM = re.compile(r"[\s,]+(GmbH & Co\.? KG|GmbH|UG \(haftungsbeschränkt\)|UG|AG|OHG|KG|OG|GbR|e\.\s?[UK]\.|PartG(?: mbB)?)$")
TRANSKRIPT_HINWEIS = "Unser Gespräch wird zur Bearbeitung Ihres Anliegens transkribiert."

TELEFON_REGELN = """\
# Besonderheiten am Telefon
- Du sprichst, du schreibst nicht: kurze Sätze, keine Aufzählungszeichen, keine Emojis, kein Markdown.
- Uhrzeiten und Daten natürlich aussprechen („Dienstag, den vierzehnten Oktober, um neun Uhr“).
- Namen, Telefonnummern und E-Mail-Adressen immer wiederholen und bestätigen lassen; E-Mail-Adressen
  buchstabieren lassen, wenn sie ungewöhnlich sind. Die Nummer des Anrufers kennst du oft schon –
  frag, ob du unter dieser Nummer zurückrufen darfst.
- Während ein Werkzeug arbeitet, kurz überbrücken („Einen Moment, ich schaue in den Kalender.“).
- Zu Beginn sagst du, dass hier ein KI-Assistent spricht (steht in der Begrüßung).
- Wenn die Person ausdrücklich einen Menschen sprechen möchte oder aufgebracht ist: Rückruf anbieten,
  mit team_benachrichtigen (Dringlichkeit hoch, Rückrufnummer, Anliegen) weitergeben.
- Verabschiede dich knapp und fasse zusammen, was vereinbart wurde.
"""


def _fuer_vapi(schema: dict) -> dict:
    """Wandelt das strikte Claude-Schema (nullable per ["typ", "null"]) in ein einfaches JSON-Schema:
    optionale Felder verlieren den null-Typ und fallen aus 'required'."""
    s = copy.deepcopy(schema["input_schema"])
    pflicht = []
    for name, prop in s["properties"].items():
        if isinstance(prop.get("type"), list):
            prop["type"] = next(t for t in prop["type"] if t != "null")
        else:
            pflicht.append(name)
    s["required"] = pflicht
    s.pop("additionalProperties", None)
    return s


def telefon_werkzeuge(agent: Agent) -> list[str]:
    """Web-Suche/-Abruf sind Anthropic-Server-Werkzeuge und am Telefon nicht verfügbar."""
    return [n for n in agent.tool_namen if n not in SERVER_WERKZEUGE]


def _vapi_name(firma: str, bezeichnung: str) -> str:
    """„Firma – Bezeichnung“ für das Vapi-Dashboard. Zu lang → erst die Rechtsform weglassen, dann den
    Firmennamen wortweise kürzen; die Bezeichnung bleibt immer ganz."""
    woerter = (RECHTSFORM.sub("", firma).strip() or firma).split()
    for f in [firma] + [" ".join(woerter[:i]) for i in range(len(woerter), 0, -1)]:
        if len(name := f"{f} – {bezeichnung}") <= VAPI_NAME_MAX:
            return name
    return bezeichnung[:VAPI_NAME_MAX]


def assistent_konfig(konfig: KundenKonfig, agent_name: str, server_url: str, token: str) -> dict:
    agent = Agent(konfig, agent_name)
    a = konfig.agent(agent_name)
    t = {**konfig.daten.get("telefon", {}), **a.get("telefon", {})}
    firma = konfig.firma["name"]

    system_teile = [PLATTFORM_REGELN, _rechtsrahmen(konfig), _firma_block(konfig), TELEFON_REGELN,
                    f"# Deine Rolle: {a.get('bezeichnung', agent_name)}\n\n" + konfig.text_datei(a["prompt"])]
    if agent.freigabe:
        system_teile.append("Diese Werkzeuge brauchen die Freigabe eines Menschen, bevor sie wirklich ausgeführt "
                            f"werden: {', '.join(sorted(agent.freigabe))}.")
    for datei in a.get("wissen", konfig.daten.get("wissen", [])):
        system_teile.append(f"# Wissensbasis ({datei})\n\n" + konfig.text_datei(datei))
    system_teile.append("Heutiges Datum und Uhrzeit: {{\"now\" | date: \"%A, %d.%m.%Y %H:%M\", \""
                        + konfig.zeitzone + "\"}}")

    endpunkt = {"url": f"{server_url.rstrip('/')}/vapi/{agent_name}",
                "headers": {"Authorization": f"Bearer {token}"}, "timeoutSeconds": 20}
    tools = [{"type": "function",
              "function": {"name": n, "description": TOOL_DEFINITIONEN[n]["description"],
                           "parameters": _fuer_vapi(TOOL_DEFINITIONEN[n])},
              "server": endpunkt}
             for n in telefon_werkzeuge(agent)]

    return {
        "name": _vapi_name(firma, a.get("bezeichnung", agent_name)),
        "firstMessage": t.get("begruessung", f"Guten Tag, hier ist der KI-Assistent von {firma}. "
                                             f"{TRANSKRIPT_HINWEIS} Wie kann ich Ihnen helfen?"),
        "endCallMessage": t.get("verabschiedung", "Vielen Dank für Ihren Anruf. Auf Wiederhören!"),
        "model": {
            "provider": "anthropic",
            "model": t.get("modell", VAPI_MODELL),
            "messages": [{"role": "system", "content": "\n\n---\n\n".join(system_teile)}],
            "tools": tools,
        },
        "transcriber": t.get("transkription", {"provider": "deepgram", "model": "nova-2", "language": "de"}),
        "voice": t.get("stimme", {"provider": "azure", "voiceId": "de-DE-KatjaNeural"}),
        "maxDurationSeconds": t.get("max_dauer_s", 900),
        # Vapi nimmt Anrufe sonst als Audio auf – wir brauchen nur das Transkript (Datensparsamkeit)
        "artifactPlan": {"recordingEnabled": bool(t.get("aufzeichnung", False))},
        "server": endpunkt,
        "serverMessages": ["tool-calls", "end-of-call-report"],
    }


def _argumente(aufruf: dict) -> dict:
    """Vapi liefert Argumente je nach Version als arguments, parameters oder function.arguments (ggf. JSON-String)."""
    args = aufruf.get("arguments", aufruf.get("parameters"))
    if args is None:
        args = (aufruf.get("function") or {}).get("arguments", {})
    if isinstance(args, str):
        args = json.loads(args or "{}")
    return args


def _auffuellen(name: str, args: dict) -> dict:
    """Nicht übergebene optionale Felder als None ergänzen, unbekannte Felder verwerfen.
    Fehlende Pflichtfelder als klare Meldung an das Vapi-Modell zurückgeben (dort ist das Schema nicht strikt)."""
    props = TOOL_DEFINITIONEN[name]["input_schema"]["properties"]
    fehlend = [f for f, p in props.items() if not isinstance(p.get("type"), list) and args.get(f) is None]
    if fehlend:
        raise ValueError(f"Pflichtfelder fehlen: {', '.join(fehlend)} – bitte mit allen Pflichtfeldern erneut aufrufen")
    return {feld: args.get(feld) for feld in props}


def vapi_nachricht(agent: Agent, payload: dict) -> dict:
    """Verarbeitet eine Server-Nachricht von Vapi und liefert die Antwort für Vapi."""
    msg = payload.get("message", {})
    typ = msg.get("type")
    anrufer = ((msg.get("call") or {}).get("customer") or {}).get("number")

    if typ == "tool-calls":
        erlaubt = set(telefon_werkzeuge(agent))
        ergebnisse = []
        for aufruf in msg.get("toolCallList", []):
            name = aufruf.get("name") or (aufruf.get("function") or {}).get("name")
            try:
                if name not in erlaubt:
                    raise ValueError(f"Werkzeug '{name}' ist für diesen Agenten nicht freigeschaltet")
                inhalt, _, _ = agent.werkzeug_ausfuehren(name, _auffuellen(name, _argumente(aufruf)), "telefon")
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                inhalt = json.dumps({"fehler": str(e)}, ensure_ascii=False)
            ergebnisse.append({"name": name, "toolCallId": aufruf.get("id"), "result": inhalt})
        return {"results": ergebnisse}

    if typ == "end-of-call-report":
        a = agent.a
        if {**agent.k.daten.get("telefon", {}), **a.get("telefon", {})}.get("nachbearbeitung", True):
            transkript = ((msg.get("artifact") or {}).get("transcript") or msg.get("transcript") or "")[:30000]
            if transkript.strip():
                auftrag = ("Ein Telefonat mit dem Telefon-Assistenten ist beendet. Nachbearbeitung: Prüfe anhand "
                           "des Transkripts, ob alles erledigt ist – Anliegen als Lead im CRM (Dubletten beachten, "
                           "ggf. aktualisieren), zugesagter Rückruf/Übergabe per team_benachrichtigen, bei gebuchtem "
                           "Termin und bekannter E-Mail eine Bestätigung. Tue nichts doppelt, was im Gespräch schon "
                           "per Werkzeug erledigt wurde (kalender_termine_suchen / crm_leads_suchen nutzen). "
                           "Erfinde nichts, was nicht im Transkript steht.\n\n"
                           f"Anrufernummer: {anrufer or 'unbekannt'}\nEnde: {msg.get('endedReason', '?')}\n\n"
                           f"<transkript>\n{transkript}\n</transkript>")
                threading.Thread(target=_nachbearbeiten, args=(agent, auftrag), daemon=True).start()
        return {}

    return {}


def _nachbearbeiten(agent: Agent, auftrag: str) -> None:
    try:
        ergebnis, _ = agent.ausfuehren(auftrag, kanal="telefon")
        agent.store.protokollieren({"agent": agent.name, "kanal": "telefon", "nachbearbeitung": ergebnis.text})
    except Exception as e:  # Hintergrund-Thread darf den Server nicht stören
        agent.store.protokollieren({"agent": agent.name, "kanal": "telefon", "fehler_nachbearbeitung": str(e)})
