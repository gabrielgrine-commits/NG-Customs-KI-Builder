"""Vapi-API-Client (https://docs.vapi.ai/api-reference) – nur Standardbibliothek.

Gemeinsame Grundlage für scripts/vapi_einrichten.py (Kommandozeile) und scripts/vapi_mcp.py
(MCP-Server für Claude Code). Braucht VAPI_TOKEN (Private Key); zum Anlegen eines Assistenten
außerdem NGC_BASIS_URL und NGC_GEHEIMNIS, damit Vapi die Werkzeuge der Plattform aufrufen kann.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import config
from .geheimnisse import kunden_url, token
from .telefon import assistent_konfig

API = "https://api.vapi.ai"
# Cloudflare vor api.vapi.ai sperrt den Python-Standard-User-Agent (HTTP 403, „error code: 1010“)
USER_AGENT = "ng-customs-ki-builder/1.0"
PLATZHALTER_URL = "https://PLATTFORM-ADRESSE.invalid"
GEHEIME_FELDER = {"authorization", "x-vapi-secret", "secret", "token", "authtoken", "twilioauthtoken",
                  "apikey", "api_key", "password", "credentialid"}


class VapiFehler(Exception):
    pass


def schluessel() -> str:
    """VAPI_TOKEN ohne mitkopierte Leerzeichen, Anführungszeichen oder „Bearer “."""
    s = os.environ.get("VAPI_TOKEN", "").strip().strip("\"'").strip()
    return s.removeprefix("Bearer ").strip()


def anfrage(methode: str, pfad: str, daten: dict | None = None, params: dict | None = None) -> Any:
    s = schluessel()
    if not s:
        raise VapiFehler("VAPI_TOKEN fehlt: Private Key aus dem Vapi-Dashboard als Umgebungsvariable setzen "
                         "(nicht in den Chat schreiben).")
    params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    url = API + pfad + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(
        url, method=methode,
        data=json.dumps(daten).encode() if daten is not None else None,
        headers={"Authorization": f"Bearer {s}", "Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as antwort:
            return json.loads(antwort.read() or b"{}")
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")[:1000]
        raise VapiFehler(f"Vapi {methode} {pfad}: HTTP {e.code} – {text}") from None
    except urllib.error.URLError as e:
        raise VapiFehler(f"Vapi nicht erreichbar: {e.reason}") from None


def maskieren(obj: Any) -> Any:
    """Tokens (z. B. der Plattform-Token im Server-Header) nie ausgeben."""
    if isinstance(obj, dict):
        return {k: "***" if k.lower() in GEHEIME_FELDER and isinstance(v, str) and v else maskieren(v)
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [maskieren(v) for v in obj]
    return obj


def assistent_bauen(kunde: str | Path, agent: str, platzhalter: bool = False) -> tuple[config.KundenKonfig, dict]:
    """Assistenten-Konfiguration aus kunden/<slug>. platzhalter=True erlaubt eine Vorschau ohne
    NGC_BASIS_URL/NGC_GEHEIMNIS (Adresse und Token sind dann Platzhalter)."""
    try:
        k = config.laden(kunde)
        a = k.agent(agent)
    except config.KonfigFehler as e:
        raise VapiFehler(str(e)) from None
    if "telefon" not in a.get("kanaele", []):
        raise VapiFehler(f"Agent '{agent}' hat den Kanal 'telefon' nicht in config.json.")
    server_url, api_token = kunden_url(k), token(k, "api")
    if not server_url.startswith("https://") or len(api_token) < 16:
        if not platzhalter:
            raise VapiFehler("NGC_BASIS_URL (https://…) und NGC_GEHEIMNIS müssen gesetzt sein – Vapi braucht die "
                             "öffentliche Plattform-Adresse, um Termine zu buchen und Leads zu speichern.")
        server_url, api_token = f"{PLATZHALTER_URL}/k/{k.kunden_dir.name}", "x" * 40
    return k, assistent_konfig(k, agent, server_url, api_token)


def vorschau(assistent: dict, prompt_zeichen: int = 300) -> dict:
    v = maskieren(json.loads(json.dumps(assistent)))
    inhalt = v["model"]["messages"][0]["content"]
    if len(inhalt) > prompt_zeichen:
        v["model"]["messages"][0]["content"] = inhalt[:prompt_zeichen] + f" … ({len(inhalt)} Zeichen)"
    return v


def nummer_finden(nummer: str) -> dict:
    """Vapi-ID oder Rufnummer (+43…/+49…) einer Nummer im Konto."""
    nummern = anfrage("GET", "/phone-number")
    treffer = next((n for n in nummern if nummer in (n.get("id"), n.get("number"))), None)
    if not treffer:
        vorhanden = "\n".join(f"  {n.get('id')} {n.get('number')}" for n in nummern) or "  (keine)"
        raise VapiFehler(f"Nummer {nummer} nicht im Vapi-Konto. Vorhanden:\n{vorhanden}")
    return treffer


def _config_schreiben(pfad: Path, roh: dict) -> None:
    pfad.write_text(json.dumps(roh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def einrichten(kunde: str | Path, agent: str, nummer: str | None = None) -> list[str]:
    """Legt den Assistenten an oder aktualisiert ihn (ID aus telefon.vapi_assistent_id) und verknüpft
    optional eine Nummer. Die ID wird sofort in config.json gespeichert – auch wenn danach etwas scheitert."""
    k, assistent = assistent_bauen(kunde, agent)
    cfg_pfad = k.agent_dir / "config.json"
    roh = json.loads(cfg_pfad.read_text(encoding="utf-8"))
    tel = roh.setdefault("telefon", {})
    meldungen = []
    if tel.get("vapi_assistent_id"):
        ergebnis = anfrage("PATCH", f"/assistant/{tel['vapi_assistent_id']}", assistent)
        meldungen.append(f"🔄 Assistent aktualisiert: {ergebnis.get('id')} ({ergebnis.get('name')})")
    else:
        ergebnis = anfrage("POST", "/assistant", assistent)
        tel["vapi_assistent_id"] = ergebnis["id"]
        _config_schreiben(cfg_pfad, roh)
        meldungen.append(f"✅ Assistent angelegt: {ergebnis['id']} ({ergebnis.get('name')})")

    if nummer:
        treffer = nummer_finden(nummer)
        anfrage("PATCH", f"/phone-number/{treffer['id']}", {"assistantId": tel["vapi_assistent_id"]})
        tel["nummer"] = treffer.get("number")
        tel["vapi_nummer_id"] = treffer["id"]
        meldungen.append(f"📞 {treffer.get('number')} ist jetzt mit dem Assistenten verbunden.")

    _config_schreiben(cfg_pfad, roh)
    meldungen.append(f"Gespeichert in {cfg_pfad} (telefon.vapi_assistent_id{', nummer' if nummer else ''}).")
    return meldungen
