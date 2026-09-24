"""Werkzeuge, mit denen die Kunden-Agenten selbstständig handeln.

Jedes Werkzeug hat eine Tool-Definition für Claude (Name, Beschreibung, JSON-Schema) und eine
Python-Funktion, die es ausführt. Web-Suche und Web-Abruf sind Server-Werkzeuge von Anthropic und
laufen ohne eigenen Code.

Anbindungen an externe Systeme (Google Kalender, HubSpot, Pipedrive …) werden hier ergänzt, indem
man die jeweilige Methode durch einen API-Aufruf ersetzt – die Tool-Definition bleibt gleich, die
Agenten-Prompts müssen dafür nicht angepasst werden.
"""

from __future__ import annotations

import json
import os
import smtplib
import urllib.request
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .config import WOCHENTAGE, KundenKonfig
from .store import JsonStore, neue_id

LEAD_STATUS = ["neu", "kontaktiert", "qualifiziert", "termin", "angebot", "gewonnen", "verloren", "kein_interesse"]


def _opt(typ: str, beschreibung: str, **extra: Any) -> dict:
    """Optionales Feld im strikten Schema: muss in 'required' stehen, darf aber null sein."""
    return {"type": [typ, "null"], "description": beschreibung, **extra}


def _schema(props: dict, beschreibung: str, name: str) -> dict:
    return {
        "name": name,
        "description": beschreibung,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": props,
            "required": list(props),
            "additionalProperties": False,
        },
    }


TOOL_DEFINITIONEN: dict[str, dict] = {
    "kalender_freie_termine": _schema(
        {
            "von_datum": {"type": "string", "description": "Erster Tag, Format YYYY-MM-DD"},
            "bis_datum": {"type": "string", "description": "Letzter Tag, Format YYYY-MM-DD (max. 14 Tage nach von_datum)"},
            "dauer_min": _opt("integer", "Dauer in Minuten; null = Standarddauer des Betriebs"),
        },
        "Liefert freie Termine im Kalender des Betriebs. Immer zuerst aufrufen, bevor Termine vorgeschlagen "
        "werden – niemals Termine aus dem Gedächtnis anbieten.",
        "kalender_freie_termine",
    ),
    "kalender_termin_buchen": _schema(
        {
            "start": {"type": "string", "description": "Beginn, Format YYYY-MM-DDTHH:MM (Ortszeit des Betriebs)"},
            "dauer_min": _opt("integer", "Dauer in Minuten; null = Standarddauer"),
            "name": {"type": "string", "description": "Vor- und Nachname der Person"},
            "kontakt": {"type": "string", "description": "E-Mail-Adresse oder Telefonnummer für die Bestätigung"},
            "anliegen": {"type": "string", "description": "Kurz: worum geht es beim Termin"},
            "lead_id": _opt("string", "ID aus dem CRM, falls vorhanden"),
        },
        "Bucht einen Termin verbindlich. Nur aufrufen, wenn die Person den konkreten Zeitpunkt ausdrücklich "
        "bestätigt hat und Name sowie Kontakt vorliegen.",
        "kalender_termin_buchen",
    ),
    "kalender_termine_suchen": _schema(
        {"suchbegriff": {"type": "string", "description": "Name, E-Mail oder Telefonnummer der Person"}},
        "Findet kommende Termine einer Person (z. B. für Verschiebung oder Absage).",
        "kalender_termine_suchen",
    ),
    "kalender_termin_stornieren": _schema(
        {
            "termin_id": {"type": "string", "description": "ID aus kalender_termine_suchen"},
            "grund": {"type": "string", "description": "Kurzer Grund der Absage"},
        },
        "Sagt einen bestehenden Termin ab. Vorher mit der Person klären, dass sie wirklich absagen will.",
        "kalender_termin_stornieren",
    ),
    "crm_lead_speichern": _schema(
        {
            "name": _opt("string", "Ansprechperson"),
            "firma": _opt("string", "Firmenname (bei Geschäftskunden)"),
            "email": _opt("string", "E-Mail-Adresse"),
            "telefon": _opt("string", "Telefonnummer"),
            "website": _opt("string", "Website (bei recherchierten Firmen-Leads)"),
            "quelle": {"type": "string", "description": "Woher der Lead kommt, z. B. 'Website-Chat', 'E-Mail', 'Web-Recherche'"},
            "anliegen": {"type": "string", "description": "Bedarf bzw. Grund, warum der Lead passt"},
            "bewertung": {"type": "integer", "description": "Passung/Kaufwahrscheinlichkeit 1 (schwach) bis 10 (heiß)"},
            "status": {"type": "string", "enum": LEAD_STATUS},
            "naechster_schritt_am": _opt("string", "Datum für Wiedervorlage/Nachfassen, YYYY-MM-DD"),
            "notiz": _opt("string", "Weitere Infos, Quellen-URL, Gesprächsverlauf in Stichworten"),
        },
        "Legt einen Lead/Kontakt im CRM an. Dubletten (gleiche E-Mail oder Website) werden erkannt und "
        "zurückgemeldet statt doppelt angelegt.",
        "crm_lead_speichern",
    ),
    "crm_leads_suchen": _schema(
        {
            "suchbegriff": _opt("string", "Freitext über Name, Firma, E-Mail, Website, Anliegen; null = alle"),
            "status": _opt("string", "Nur Leads mit diesem Status: " + ", ".join(LEAD_STATUS)),
            "faellig_bis": _opt("string", "Nur Leads mit naechster_schritt_am <= diesem Datum (YYYY-MM-DD)"),
        },
        "Durchsucht das CRM. Nutzen, um Dubletten zu vermeiden und fällige Wiedervorlagen zu finden.",
        "crm_leads_suchen",
    ),
    "crm_lead_aktualisieren": _schema(
        {
            "lead_id": {"type": "string"},
            "status": _opt("string", "Neuer Status: " + ", ".join(LEAD_STATUS)),
            "bewertung": _opt("integer", "Neue Bewertung 1-10"),
            "naechster_schritt_am": _opt("string", "Neues Wiedervorlagedatum YYYY-MM-DD"),
            "notiz": _opt("string", "Wird mit Zeitstempel an die Historie angehängt"),
        },
        "Aktualisiert Status, Bewertung oder Wiedervorlage eines Leads und ergänzt die Historie.",
        "crm_lead_aktualisieren",
    ),
    "email_senden": _schema(
        {
            "an": {"type": "string", "description": "Empfänger-E-Mail-Adresse"},
            "betreff": {"type": "string"},
            "text": {"type": "string", "description": "Vollständiger E-Mail-Text inkl. Anrede und Grußformel"},
            "lead_id": _opt("string", "Zugehöriger Lead, damit die E-Mail in der Historie landet"),
        },
        "Sendet eine E-Mail im Namen des Betriebs. Je nach Einstellung wird sie sofort versendet oder dem "
        "Team zur Freigabe vorgelegt – das Ergebnis sagt, was passiert ist.",
        "email_senden",
    ),
    "team_benachrichtigen": _schema(
        {
            "betreff": {"type": "string"},
            "nachricht": {"type": "string", "description": "Was ist passiert, was soll das Team tun, alle nötigen Kontaktdaten"},
            "dringlichkeit": {"type": "string", "enum": ["niedrig", "normal", "hoch"]},
        },
        "Informiert die Inhaber/das Team (Übergabe an einen Menschen). Nutzen bei Beschwerden, Notfällen, "
        "Sonderwünschen, heißen Leads oder wenn du nicht sicher weiterweißt.",
        "team_benachrichtigen",
    ),
}

SERVER_WERKZEUGE = {
    "web_suche": {"type": "web_search_20260209", "name": "web_search", "max_uses": 10,
                  "user_location": {"type": "approximate", "country": "DE"}},
    "web_abruf": {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 20},
}


class Werkzeuge:
    def __init__(self, konfig: KundenKonfig, store: JsonStore, trockenlauf: bool = False):
        self.k = konfig
        self.store = store
        # trockenlauf: keine echten E-Mails/Webhooks (für Tests)
        self.trockenlauf = trockenlauf
        self.tz = ZoneInfo(konfig.zeitzone)
        self._fn: dict[str, Callable[..., Any]] = {
            "kalender_freie_termine": self.kalender_freie_termine,
            "kalender_termin_buchen": self.kalender_termin_buchen,
            "kalender_termine_suchen": self.kalender_termine_suchen,
            "kalender_termin_stornieren": self.kalender_termin_stornieren,
            "crm_lead_speichern": self.crm_lead_speichern,
            "crm_leads_suchen": self.crm_leads_suchen,
            "crm_lead_aktualisieren": self.crm_lead_aktualisieren,
            "email_senden": self.email_senden,
            "team_benachrichtigen": self.team_benachrichtigen,
        }

    # ------------------------------------------------------------------ Registry

    def definitionen(self, namen: list[str]) -> list[dict]:
        defs = []
        for n in namen:
            if n in SERVER_WERKZEUGE:
                defs.append(SERVER_WERKZEUGE[n])
            else:
                defs.append(TOOL_DEFINITIONEN[n])
        return defs

    def ausfuehren(self, name: str, eingabe: dict) -> Any:
        if name not in self._fn:
            raise ValueError(f"Unbekanntes Werkzeug: {name}")
        return self._fn[name](**eingabe)

    # ------------------------------------------------------------------ Kalender

    @property
    def _kal(self) -> dict:
        return self.k.daten.get("kalender", {})

    def _jetzt(self) -> datetime:
        return datetime.now(self.tz).replace(tzinfo=None, second=0, microsecond=0)

    def _termine(self) -> list[dict]:
        return self.store.lesen("termine", [])

    def _ist_frei(self, start: datetime, dauer: int, termine: list[dict]) -> bool:
        puffer = timedelta(minutes=self._kal.get("puffer_min", 0))
        ende = start + timedelta(minutes=dauer)
        for t in termine:
            if t["status"] != "bestaetigt":
                continue
            ts = datetime.fromisoformat(t["start"])
            te = ts + timedelta(minutes=t["dauer_min"])
            if start < te + puffer and ts < ende + puffer:
                return False
        return True

    def _im_arbeitsfenster(self, start: datetime, dauer: int) -> bool:
        if start.date().isoformat() in self._kal.get("gesperrte_tage", []):
            return False
        tag = WOCHENTAGE[start.weekday()]
        ende = start + timedelta(minutes=dauer)
        for von, bis in self._kal.get("arbeitszeiten", {}).get(tag, []):
            f_von = datetime.combine(start.date(), datetime.strptime(von, "%H:%M").time())
            f_bis = datetime.combine(start.date(), datetime.strptime(bis, "%H:%M").time())
            if f_von <= start and ende <= f_bis:
                return True
        return False

    def _fruehester_start(self) -> datetime:
        return self._jetzt() + timedelta(hours=self._kal.get("vorlauf_stunden", 2))

    def kalender_freie_termine(self, von_datum: str, bis_datum: str, dauer_min: int | None = None) -> dict:
        dauer = dauer_min or self._kal.get("termindauer_min", 60)
        raster = timedelta(minutes=self._kal.get("raster_min", 30))
        von = max(date.fromisoformat(von_datum), self._jetzt().date())
        bis = min(date.fromisoformat(bis_datum), von + timedelta(days=14),
                  self._jetzt().date() + timedelta(days=self._kal.get("max_tage_voraus", 60)))
        termine = self._termine()
        fruehestens = self._fruehester_start()
        frei: list[str] = []
        tag = von
        while tag <= bis and len(frei) < 30:
            for fenster_von, _ in self._kal.get("arbeitszeiten", {}).get(WOCHENTAGE[tag.weekday()], []):
                slot = datetime.combine(tag, datetime.strptime(fenster_von, "%H:%M").time())
                while self._im_arbeitsfenster(slot, dauer):
                    if slot >= fruehestens and self._ist_frei(slot, dauer, termine):
                        frei.append(slot.strftime("%Y-%m-%dT%H:%M"))
                    slot += raster
            tag += timedelta(days=1)
        return {"dauer_min": dauer, "freie_termine": frei,
                "hinweis": None if frei else "Keine freien Termine im Zeitraum – späteren Zeitraum prüfen."}

    def kalender_termin_buchen(self, start: str, name: str, kontakt: str, anliegen: str,
                               dauer_min: int | None = None, lead_id: str | None = None) -> dict:
        dauer = dauer_min or self._kal.get("termindauer_min", 60)
        beginn = datetime.fromisoformat(start)
        if beginn < self._fruehester_start():
            return {"fehler": "Zeitpunkt liegt zu kurzfristig oder in der Vergangenheit."}
        if not self._im_arbeitsfenster(beginn, dauer):
            return {"fehler": "Zeitpunkt liegt außerhalb der Arbeitszeiten. kalender_freie_termine nutzen."}

        def buchen(termine: list[dict]) -> dict:
            if not self._ist_frei(beginn, dauer, termine):
                return {"fehler": "Dieser Termin ist inzwischen vergeben. Bitte Alternativen anbieten."}
            termin = {"id": neue_id("T"), "start": beginn.strftime("%Y-%m-%dT%H:%M"), "dauer_min": dauer,
                      "name": name, "kontakt": kontakt, "anliegen": anliegen, "lead_id": lead_id,
                      "status": "bestaetigt", "gebucht_am": self._jetzt().isoformat()}
            termine.append(termin)
            return {"gebucht": True, "termin": termin}

        return self.store.aendern("termine", [], buchen)

    def kalender_termine_suchen(self, suchbegriff: str) -> dict:
        s = suchbegriff.lower().strip()
        jetzt = self._jetzt()
        treffer = [t for t in self._termine()
                   if t["status"] == "bestaetigt" and datetime.fromisoformat(t["start"]) >= jetzt
                   and (s in t["name"].lower() or s in t["kontakt"].lower())]
        return {"termine": treffer}

    def kalender_termin_stornieren(self, termin_id: str, grund: str) -> dict:
        def stornieren(termine: list[dict]) -> dict:
            for t in termine:
                if t["id"] == termin_id and t["status"] == "bestaetigt":
                    t["status"] = "storniert"
                    t["storno_grund"] = grund
                    return {"storniert": True, "termin": t}
            return {"fehler": f"Kein aktiver Termin mit ID {termin_id}"}

        return self.store.aendern("termine", [], stornieren)

    def kalender_ics(self) -> str:
        """iCalendar-Feed aller bestätigten Termine – im Google-/Outlook-Kalender abonnierbar."""
        zeilen = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//NG Customs//{self.k.firma['name']}//DE",
                  f"X-WR-TIMEZONE:{self.k.zeitzone}"]
        for t in self._termine():
            if t["status"] != "bestaetigt":
                continue
            s = datetime.fromisoformat(t["start"])
            e = s + timedelta(minutes=t["dauer_min"])
            beschreibung = f"{t['anliegen']} | Kontakt: {t['kontakt']}".replace("\n", " ").replace(",", "\\,")
            zeilen += ["BEGIN:VEVENT", f"UID:{t['id']}@ng-customs",
                       f"DTSTART;TZID={self.k.zeitzone}:{s:%Y%m%dT%H%M%S}",
                       f"DTEND;TZID={self.k.zeitzone}:{e:%Y%m%dT%H%M%S}",
                       f"SUMMARY:{t['name']}", f"DESCRIPTION:{beschreibung}", "END:VEVENT"]
        zeilen.append("END:VCALENDAR")
        return "\r\n".join(zeilen) + "\r\n"

    # ------------------------------------------------------------------ CRM

    def crm_lead_speichern(self, quelle: str, anliegen: str, bewertung: int, status: str,
                           name: str | None = None, firma: str | None = None, email: str | None = None,
                           telefon: str | None = None, website: str | None = None,
                           naechster_schritt_am: str | None = None, notiz: str | None = None) -> dict:
        if not (email or telefon or website):
            return {"fehler": "Mindestens E-Mail, Telefon oder Website angeben."}

        def domain(url: str | None) -> str | None:
            if not url:
                return None
            return url.lower().split("//")[-1].split("/")[0].removeprefix("www.")

        def speichern(leads: list[dict]) -> dict:
            for l in leads:
                if (email and l.get("email", "").lower() == email.lower()) or \
                   (website and domain(l.get("website")) == domain(website)):
                    return {"dublette": True, "lead_id": l["id"], "status": l["status"],
                            "hinweis": "Lead existiert bereits – ggf. crm_lead_aktualisieren nutzen."}
            lead = {"id": neue_id("L"), "name": name, "firma": firma, "email": email, "telefon": telefon,
                    "website": website, "quelle": quelle, "anliegen": anliegen,
                    "bewertung": max(1, min(10, bewertung)), "status": status,
                    "naechster_schritt_am": naechster_schritt_am, "angelegt_am": self._jetzt().isoformat(),
                    "historie": [{"zeit": self._jetzt().isoformat(), "notiz": notiz or "angelegt"}]}
            leads.append(lead)
            return {"gespeichert": True, "lead_id": lead["id"]}

        return self.store.aendern("crm", [], speichern)

    def crm_leads_suchen(self, suchbegriff: str | None = None, status: str | None = None,
                         faellig_bis: str | None = None) -> dict:
        leads = self.store.lesen("crm", [])
        s = (suchbegriff or "").lower()
        treffer = []
        for l in leads:
            if status and l["status"] != status:
                continue
            if faellig_bis and not (l.get("naechster_schritt_am") and l["naechster_schritt_am"] <= faellig_bis):
                continue
            text = " ".join(str(l.get(f) or "") for f in ("name", "firma", "email", "website", "anliegen")).lower()
            if s and s not in text:
                continue
            kurz = {k: v for k, v in l.items() if k != "historie"}
            kurz["letzte_notizen"] = l.get("historie", [])[-3:]
            treffer.append(kurz)
        return {"anzahl": len(treffer), "leads": treffer[:50]}

    def crm_lead_aktualisieren(self, lead_id: str, status: str | None = None, bewertung: int | None = None,
                               naechster_schritt_am: str | None = None, notiz: str | None = None) -> dict:
        if status and status not in LEAD_STATUS:
            return {"fehler": f"Unbekannter Status '{status}'. Erlaubt: {', '.join(LEAD_STATUS)}"}

        def aktualisieren(leads: list[dict]) -> dict:
            for l in leads:
                if l["id"] == lead_id:
                    if status:
                        l["status"] = status
                    if bewertung:
                        l["bewertung"] = max(1, min(10, bewertung))
                    if naechster_schritt_am is not None:
                        l["naechster_schritt_am"] = naechster_schritt_am
                    if notiz:
                        l.setdefault("historie", []).append({"zeit": self._jetzt().isoformat(), "notiz": notiz})
                    return {"aktualisiert": True, "lead_id": lead_id, "status": l["status"]}
            return {"fehler": f"Lead {lead_id} nicht gefunden"}

        return self.store.aendern("crm", [], aktualisieren)

    # ------------------------------------------------------------------ Kommunikation

    def _smtp_zugang(self) -> tuple[str, str] | None:
        e = self.k.daten.get("email", {})
        benutzer = os.environ.get(e.get("benutzer_env", ""), "")
        passwort = os.environ.get(e.get("passwort_env", ""), "")
        if e.get("smtp_host") and benutzer and passwort:
            return benutzer, passwort
        return None

    def _smtp_senden(self, an: str, betreff: str, text: str) -> str:
        e = self.k.daten["email"]
        msg = EmailMessage()
        msg["From"] = f"{self.k.firma['name']} <{e['absender']}>"
        msg["To"] = an
        msg["Subject"] = betreff
        msg.set_content(text)
        if self.trockenlauf:
            return "trockenlauf"
        zugang = self._smtp_zugang()
        if not zugang:
            ausgang = self.k.daten_dir / "postausgang"
            ausgang.mkdir(parents=True, exist_ok=True)
            datei = ausgang / f"{datetime.now():%Y%m%d-%H%M%S}-{neue_id('M')}.eml"
            datei.write_bytes(bytes(msg))
            return f"nicht versendet (SMTP nicht konfiguriert) – gespeichert unter {datei.name}"
        with smtplib.SMTP(e["smtp_host"], int(e.get("smtp_port", 587)), timeout=30) as s:
            s.starttls()
            s.login(*zugang)
            s.send_message(msg)
        return "versendet"

    def email_senden(self, an: str, betreff: str, text: str, lead_id: str | None = None) -> dict:
        sperrliste = {a.lower() for a in self.store.lesen("sperrliste", [])}
        if an.lower() in sperrliste:
            return {"fehler": "Empfänger hat Werbung/Kontakt widersprochen (Sperrliste). Nicht anschreiben."}
        ergebnis = self._smtp_senden(an, betreff, text)
        if lead_id:
            self.crm_lead_aktualisieren(lead_id, notiz=f"E-Mail '{betreff}' an {an}: {ergebnis}")
        return {"ergebnis": ergebnis}

    def team_benachrichtigen(self, betreff: str, nachricht: str, dringlichkeit: str) -> dict:
        b = self.k.daten.get("benachrichtigung", {})
        eintrag = {"zeit": self._jetzt().isoformat(), "betreff": betreff, "nachricht": nachricht,
                   "dringlichkeit": dringlichkeit}
        self.store.aendern("benachrichtigungen", [], lambda liste: liste.append(eintrag))
        wege = ["gespeichert"]
        if self.trockenlauf:
            return {"zugestellt": wege + ["trockenlauf"]}
        if b.get("webhook_url"):
            try:
                req = urllib.request.Request(b["webhook_url"], data=json.dumps(eintrag).encode(),
                                             headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=10)
                wege.append("webhook")
            except OSError as ex:
                wege.append(f"webhook fehlgeschlagen: {ex}")
        if b.get("email"):
            try:
                prefix = "[DRINGEND] " if dringlichkeit == "hoch" else ""
                wege.append("email: " + self._smtp_senden(b["email"], f"{prefix}KI-Agent: {betreff}", nachricht))
            except (OSError, smtplib.SMTPException) as ex:
                wege.append(f"email fehlgeschlagen: {ex}")
        return {"zugestellt": wege}
