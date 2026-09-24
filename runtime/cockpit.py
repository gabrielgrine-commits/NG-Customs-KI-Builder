"""Daten und Aktionen für das Kunden-Cockpit (Web-Oberfläche für den Betrieb).

Der Betrieb gibt dort vorbereitete E-Mails frei (auch bearbeitet), sieht Leads, Termine, Berichte
und Kennzahlen – ohne dass NG Customs dafür etwas tun muss.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta

from .config import KundenKonfig
from .engine import freigabe_bearbeiten
from .geheimnisse import zugaenge
from .store import JsonStore
from .werkzeuge import LEAD_STATUS, Werkzeuge

PROTOKOLL_ZEILEN = 20000
BEARBEITBAR = {"betreff", "text"}


def _protokoll(store: JsonStore, seit: datetime) -> list[dict]:
    pfad = store.dir / "protokoll.jsonl"
    if not pfad.exists():
        return []
    zeilen = pfad.read_text(encoding="utf-8").splitlines()[-PROTOKOLL_ZEILEN:]
    eintraege = []
    for z in zeilen:
        try:
            e = json.loads(z)
        except json.JSONDecodeError:
            continue
        if e.get("zeit", "") >= seit.isoformat(timespec="seconds"):
            eintraege.append(e)
    return eintraege


def kennzahlen(konfig: KundenKonfig, store: JsonStore, tage: int = 30) -> dict:
    eintraege = _protokoll(store, datetime.now() - timedelta(days=tage))
    anfragen = Counter(e.get("kanal", "?") for e in eintraege if e.get("ereignis") == "anfrage")

    def erfolgreich(werkzeug: str, schluessel: str) -> int:
        return sum(1 for e in eintraege if e.get("werkzeug") == werkzeug
                   and isinstance(e.get("ergebnis"), dict) and e["ergebnis"].get(schluessel))

    minuten = konfig.daten.get("cockpit", {}).get("minuten_pro_anfrage", 4)
    gesamt = sum(anfragen.values())
    return {
        "zeitraum_tage": tage,
        "anfragen_gesamt": gesamt,
        "anfragen_nach_kanal": dict(anfragen),
        "termine_gebucht": erfolgreich("kalender_termin_buchen", "gebucht"),
        "leads_angelegt": erfolgreich("crm_lead_speichern", "gespeichert"),
        "team_benachrichtigt": sum(1 for e in eintraege if e.get("werkzeug") == "team_benachrichtigen"),
        "freigaben_bearbeitet": sum(1 for e in eintraege if e.get("freigabe")),
        "geschaetzte_stunden_gespart": round(gesamt * minuten / 60, 1),
        "annahme_minuten_pro_anfrage": minuten,
    }


def uebersicht(konfig: KundenKonfig) -> dict:
    store = JsonStore(konfig.daten_dir)
    freigaben = store.lesen("freigaben", [])
    offene = [f for f in freigaben if f["status"] == "offen"]
    erledigte = [f for f in freigaben if f["status"] != "offen"][-20:]
    leads = sorted(store.lesen("crm", []), key=lambda l: (l["status"] in ("gewonnen", "verloren", "kein_interesse"),
                                                           -l.get("bewertung", 0)))
    jetzt = datetime.now().strftime("%Y-%m-%dT%H:%M")
    termine = sorted((t for t in store.lesen("termine", []) if t["status"] == "bestaetigt" and t["start"] >= jetzt),
                     key=lambda t: t["start"])
    links = {k: v for k, v in zugaenge(konfig).items() if k != "cockpit"}
    return {
        "firma": konfig.firma["name"],
        "demo": bool(konfig.daten.get("demo")),
        "agenten": [{"name": n, "bezeichnung": a.get("bezeichnung", n), "kanaele": a.get("kanaele", []),
                     "freigabe": a.get("freigabe_erforderlich", [])} for n, a in konfig.daten["agenten"].items()],
        "kennzahlen": kennzahlen(konfig, store),
        "freigaben_offen": offene,
        "freigaben_erledigt": list(reversed(erledigte)),
        "leads": leads[:200],
        "lead_status": LEAD_STATUS,
        "termine": termine[:100],
        "berichte": list(reversed(store.lesen("berichte", [])[-10:])),
        "benachrichtigungen": list(reversed(store.lesen("benachrichtigungen", [])[-20:])),
        "links": links,
    }


def freigabe(konfig: KundenKonfig, daten: dict) -> dict:
    aktion = daten.get("aktion")
    if aktion not in ("freigeben", "ablehnen"):
        return {"fehler": "aktion muss 'freigeben' oder 'ablehnen' sein"}
    eingabe = daten.get("eingabe")
    if eingabe is not None and not isinstance(eingabe, dict):
        return {"fehler": "eingabe muss ein Objekt sein"}
    if eingabe is not None:
        # Nur Betreff und Text sind bearbeitbar. Empfänger & Co. bleiben wie vom Agenten vorbereitet –
        # sonst könnte ein weitergeleiteter Cockpit-Link Mails an beliebige Adressen verschicken.
        original = next((f for f in JsonStore(konfig.daten_dir).lesen("freigaben", [])
                         if f["id"] == daten.get("id")), None)
        if original:
            eingabe = {k: (str(eingabe[k])[:20000] if k in BEARBEITBAR and k in eingabe else v)
                       for k, v in original["eingabe"].items()}
    return freigabe_bearbeiten(konfig, str(daten.get("id", "")), aktion == "freigeben", eingabe)


def lead_aendern(konfig: KundenKonfig, daten: dict) -> dict:
    store = JsonStore(konfig.daten_dir)
    status = daten.get("status") or None
    notiz = (daten.get("notiz") or "").strip()[:2000] or None
    ergebnis = Werkzeuge(konfig, store).crm_lead_aktualisieren(
        str(daten.get("id", "")), status=status,
        notiz=f"[Cockpit] {notiz}" if notiz else ("[Cockpit] Status geändert" if status else None))
    store.protokollieren({"cockpit": "lead", "id": daten.get("id"), "ergebnis": ergebnis})
    return ergebnis


def sperren(konfig: KundenKonfig, daten: dict) -> dict:
    """E-Mail-Adresse auf die Sperrliste (Widerspruch gegen Kontakt/Werbung)."""
    adresse = str(daten.get("email", "")).strip().lower()
    if "@" not in adresse:
        return {"fehler": "Ungültige E-Mail-Adresse"}
    store = JsonStore(konfig.daten_dir)
    store.aendern("sperrliste", [], lambda l: None if adresse in l else l.append(adresse))
    store.protokollieren({"cockpit": "sperrliste", "email": adresse})
    return {"gesperrt": adresse}
