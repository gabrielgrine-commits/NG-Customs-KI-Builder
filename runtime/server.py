"""HTTP-Server: Website-Chat, Webhooks, Telefon (Vapi), Kalender-Feed, Demo-Seite und Kunden-Cockpit.

Endpunkte eines Kunden (Einzelbetrieb direkt unter /, auf der Plattform unter /k/<slug>/):
  GET  widget.js                  Chat-Widget zum Einbinden auf der Kunden-Website
  GET  demo                       Demo-Seite mit dem Chat (für Vertrieb und Abnahme)
  GET  cockpit                    Kunden-Cockpit (Daten nur mit Token, Link: …/cockpit#t=<Token>)
  POST chat/<agent>               {"sitzung": "...", "nachricht": "..."} -> {"antwort": "..."}
  POST webhook/<agent>            beliebiges JSON (z. B. Kontaktformular); Header X-Token
  POST vapi/<agent>               Telefon: Werkzeugaufrufe + Anrufberichte von Vapi (Bearer-Token)
  POST synthflow/<agent>/<werkzeug>  Telefon über Synthflow: Custom Action (Body = Werkzeug-Eingabe)
  POST synthflow/<agent>/nach-anruf  Synthflow Post-Call-Webhook (Transkript → Nachbearbeitung)
  GET  kalender.ics?token=…       Termin-Feed zum Abonnieren in Google/Outlook
Global: GET /gesundheit

Nur Standardbibliothek. Für Produktion hinter einen HTTPS-Reverse-Proxy (deploy/: Caddy).
"""

from __future__ import annotations

import hmac
import html
import json
import threading
import time
from collections import OrderedDict, defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from . import cockpit
from .config import KundenKonfig
from .engine import Agent, AgentFehler
from .geheimnisse import token
from .store import JsonStore
from .telefon import synthflow_nach_anruf, synthflow_werkzeug, vapi_nachricht
from .werkzeuge import Werkzeuge

STATIC = Path(__file__).parent / "static"
MAX_NACHRICHT = 2000
MAX_SITZUNGEN = 500
MAX_RUNDEN = 30
ANFRAGEN_PRO_MINUTE = 12

_anfragen: defaultdict[str, deque] = defaultdict(deque)
_anfragen_lock = threading.Lock()


def _limit_ueberschritten(ip: str) -> bool:
    with _anfragen_lock:
        q, jetzt = _anfragen[ip], time.time()
        while q and q[0] < jetzt - 60:
            q.popleft()
        q.append(jetzt)
        return len(q) > ANFRAGEN_PRO_MINUTE


def _gleich(wert: str, soll: str) -> bool:
    return bool(soll) and hmac.compare_digest(wert.encode(), soll.encode())


class Sitzungen:
    """Chat-Verläufe im Speicher (gehen bei Neustart verloren – für Website-Chats unkritisch)."""

    def __init__(self) -> None:
        self._daten: OrderedDict[str, list] = OrderedDict()
        self._sperren: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
        self._lock = threading.Lock()

    def sperre(self, sid: str) -> threading.Lock:
        with self._lock:
            return self._sperren[sid]

    def holen(self, sid: str) -> list:
        with self._lock:
            return list(self._daten.get(sid, []))

    def setzen(self, sid: str, verlauf: list) -> None:
        with self._lock:
            self._daten[sid] = verlauf
            self._daten.move_to_end(sid)
            while len(self._daten) > MAX_SITZUNGEN:
                alt, _ = self._daten.popitem(last=False)
                self._sperren.pop(alt, None)


class KundenApp:
    """Alle Endpunkte eines Kunden. Zustand (Agenten, Chat-Sitzungen) lebt hier."""

    def __init__(self, konfig: KundenKonfig, sitzungen: Sitzungen | None = None):
        self.k = konfig
        self.origins = set(konfig.daten.get("server", {}).get("erlaubte_origins", []))
        self.sitzungen = sitzungen or Sitzungen()
        self._agenten: dict[str, Agent] = {}
        self._lock = threading.Lock()

    def agent_fuer(self, name: str, kanal: str) -> Agent | None:
        a = self.k.daten["agenten"].get(name)
        if not a or kanal not in a.get("kanaele", []):
            return None
        with self._lock:
            if name not in self._agenten:
                self._agenten[name] = Agent(self.k, name)
            return self._agenten[name]

    # ------------------------------------------------------------------ GET

    def get(self, h: "Handler", pfad: str, query: dict) -> None:
        if pfad in ("", "demo"):
            h.antwort(200, self._demo_seite(), "text/html")
        elif pfad == "widget.js":
            h.antwort(200, (STATIC / "widget.js").read_text(encoding="utf-8"), "application/javascript")
        elif pfad == "cockpit":
            h.antwort(200, (STATIC / "cockpit.html").read_text(encoding="utf-8"), "text/html")
        elif pfad == "cockpit/daten":
            if self._cockpit_ok(h):
                h.antwort(200, cockpit.uebersicht(self.k))
        elif pfad == "kalender.ics":
            if not _gleich(query.get("token", [""])[0], token(self.k, "api")):
                h.antwort(403, {"fehler": "Token ungültig"})
                return
            h.antwort(200, Werkzeuge(self.k, JsonStore(self.k.daten_dir)).kalender_ics(), "text/calendar")
        else:
            h.antwort(404, {"fehler": "nicht gefunden"})

    def _demo_seite(self) -> str:
        f = self.k.firma
        agent = next((n for n, a in self.k.daten["agenten"].items() if "chat" in a.get("kanaele", [])), "")
        design = self.k.daten.get("design", {})
        e = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731
        telefon = self.k.daten.get("telefon", {}).get("nummer")
        seite = (STATIC / "demo.html").read_text(encoding="utf-8")
        ersetzungen = {
            "{{FIRMA}}": e(f["name"]),
            "{{AGENT}}": e(agent),
            "{{TITEL}}": e(self.k.daten["agenten"].get(agent, {}).get("bezeichnung", "Digitale Rezeption")),
            "{{FARBE}}": e(design.get("farbe", "#1f6feb")),
            "{{DATENSCHUTZ}}": e(f.get("datenschutz_url", "")),
            "{{WEBSITE}}": e(f.get("website", "")),
            "{{TELEFON}}": (f'<p class="tel">Oder rufen Sie den Telefon-Assistenten an: '
                            f'<a href="tel:{e(telefon)}">{e(telefon)}</a></p>' if telefon else ""),
            "{{HINWEIS}}": ("Demo-Version: Buchungen und E-Mails werden nur simuliert."
                            if self.k.daten.get("demo") else ""),
        }
        for alt, neu in ersetzungen.items():
            seite = seite.replace(alt, neu)
        return seite

    def _cockpit_ok(self, h: "Handler") -> bool:
        if _gleich(h.headers.get("X-Cockpit-Token", ""), token(self.k, "cockpit")):
            return True
        h.antwort(403, {"fehler": "Zugang ungültig – bitte den Link aus der E-Mail verwenden."})
        return False

    # ------------------------------------------------------------------ POST

    def post(self, h: "Handler", pfad: str) -> None:
        teile = pfad.split("/")
        if teile[0] == "cockpit" and len(teile) == 2:
            if not self._cockpit_ok(h):
                return
            body = h.json_body()
            aktionen: dict[str, Callable[[KundenKonfig, dict], dict]] = {
                "freigabe": cockpit.freigabe, "lead": cockpit.lead_aendern, "sperren": cockpit.sperren}
            if teile[1] not in aktionen or body is None:
                h.antwort(400, {"fehler": "Ungültige Anfrage"})
                return
            h.antwort(200, aktionen[teile[1]](self.k, body))
            return
        if teile[0] == "synthflow" and len(teile) == 3:
            self._synthflow(h, teile[1], teile[2])
            return
        if len(teile) != 2 or teile[0] not in ("chat", "webhook", "vapi"):
            h.antwort(404, {"fehler": "nicht gefunden"})
            return
        art, name = teile
        if art == "vapi":
            self._vapi(h, name)
            return
        if _limit_ueberschritten(h.client_ip()):
            h.antwort(429, {"fehler": "Zu viele Anfragen – bitte kurz warten."})
            return
        agent = self.agent_fuer(name, art)
        if not agent:
            h.antwort(404, {"fehler": f"Agent '{name}' ist für '{art}' nicht freigeschaltet"})
            return
        body = h.json_body()
        if body is None:
            h.antwort(400, {"fehler": "Ungültiges JSON"})
            return
        if art == "webhook":
            self._webhook(h, agent, body)
        else:
            self._chat(h, agent, body)

    def _webhook(self, h: "Handler", agent: Agent, body: dict) -> None:
        if not _gleich(h.headers.get("X-Token", ""), token(self.k, "api")):
            h.antwort(403, {"fehler": "Token ungültig"})
            return
        eingang = json.dumps(body, ensure_ascii=False, indent=2)[:20000]
        auftrag = ("Neuer Eingang über Webhook (z. B. Kontaktformular oder Telefon-Transkript). "
                   f"Bearbeite ihn vollständig gemäß deiner Rolle.\n\n<eingang>\n{eingang}\n</eingang>")
        try:
            ergebnis, _ = agent.ausfuehren(auftrag, kanal="webhook")
            h.antwort(200, {"ok": True, "aktionen": len(ergebnis.aktionen), "bericht": ergebnis.text})
        except Exception as e:
            print(f"FEHLER (webhook {self.k.kunden_dir.name}): {type(e).__name__}: {e}", flush=True)
            h.antwort(502, {"fehler": str(e) if isinstance(e, AgentFehler) else "interner Fehler"})

    def _chat(self, h: "Handler", agent: Agent, body: dict) -> None:
        nachricht = str(body.get("nachricht", "")).strip()[:MAX_NACHRICHT]
        sid = str(body.get("sitzung", ""))[:64]
        if not nachricht or not sid:
            h.antwort(400, {"fehler": "'sitzung' und 'nachricht' erforderlich"})
            return
        with self.sitzungen.sperre(sid):
            verlauf = self.sitzungen.holen(sid)
            if len(verlauf) > MAX_RUNDEN * 4:
                h.antwort(200, {"antwort": "Dieses Gespräch ist sehr lang geworden. Bitte laden Sie die "
                                           "Seite neu oder kontaktieren Sie uns direkt."})
                return
            try:
                ergebnis, verlauf = agent.ausfuehren(nachricht, verlauf, kanal="chat")
                self.sitzungen.setzen(sid, verlauf)
                h.antwort(200, {"antwort": ergebnis.text})
            except Exception as e:  # Besucher bekommt immer eine Antwort, Details nur ins Log
                print(f"FEHLER (chat {self.k.kunden_dir.name}): {type(e).__name__}: {e}", flush=True)
                tel = self.k.firma.get("telefon", "")
                h.antwort(200, {"antwort": "Entschuldigung, gerade gibt es eine technische Störung. "
                                           + (f"Sie erreichen uns telefonisch unter {tel}." if tel else "")})

    def _synthflow(self, h: "Handler", name: str, aktion: str) -> None:
        """Synthflow: POST synthflow/<agent>/<werkzeug> (Custom Action) oder synthflow/<agent>/nach-anruf."""
        auth = h.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not _gleich(auth or h.headers.get("X-Token", ""), token(self.k, "api")):
            h.antwort(403, {"fehler": "Token ungültig"})
            return
        agent = self.agent_fuer(name, "telefon")
        body = h.json_body()
        if not agent or body is None:
            h.antwort(404 if not agent else 400, {"fehler": "Agent nicht für Telefon freigeschaltet"
                                                   if not agent else "Ungültiges JSON"})
            return
        try:
            if aktion == "nach-anruf":
                h.antwort(200, synthflow_nach_anruf(agent, body))
            else:
                h.antwort(200, synthflow_werkzeug(agent, aktion, body))
        except Exception as e:
            print(f"FEHLER (synthflow {self.k.kunden_dir.name}): {type(e).__name__}: {e}", flush=True)
            h.antwort(500, {"fehler": "interner Fehler"})

    def _vapi(self, h: "Handler", name: str) -> None:
        auth = h.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not _gleich(auth or h.headers.get("X-Vapi-Secret", ""), token(self.k, "api")):
            h.antwort(403, {"fehler": "Token ungültig"})
            return
        agent = self.agent_fuer(name, "telefon")
        body = h.json_body()
        if not agent:
            h.antwort(404, {"fehler": "Agent nicht für Telefon freigeschaltet"})
            return
        if body is None:
            h.antwort(400, {"fehler": "Ungültiges JSON"})
            return
        try:
            h.antwort(200, vapi_nachricht(agent, body))
        except Exception as e:
            print(f"FEHLER (vapi {self.k.kunden_dir.name}): {type(e).__name__}: {e}", flush=True)
            h.antwort(500, {"fehler": "interner Fehler"})


# Auflöser: Pfad -> (KundenApp, Restpfad) oder (None, "")
Aufloeser = Callable[[str], "tuple[KundenApp | None, str]"]


class Handler(BaseHTTPRequestHandler):
    server_version = "NGCustomsAgent/1.0"
    aufloesen: Aufloeser  # wird in erstelle_server gesetzt
    app: KundenApp | None = None

    def client_ip(self) -> str:
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def _cors(self) -> None:
        origin = self.headers.get("Origin", "")
        if self.app and origin and (origin in self.app.origins or "*" in self.app.origins):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def antwort(self, code: int, inhalt: dict | str, typ: str = "application/json") -> None:
        body = (json.dumps(inhalt, ensure_ascii=False, default=str) if isinstance(inhalt, dict) else inhalt).encode()
        self.send_response(code)
        self.send_header("Content-Type", f"{typ}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if typ == "text/html":
            self.send_header("Referrer-Policy", "no-referrer")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def json_body(self) -> dict | None:
        laenge = int(self.headers.get("Content-Length", 0) or 0)
        if laenge > 100_000:
            return None
        try:
            daten = json.loads(self.rfile.read(laenge) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return daten if isinstance(daten, dict) else None

    def _app(self) -> tuple[KundenApp | None, str, dict]:
        url = urlparse(self.path)
        app, rest = type(self).aufloesen(url.path)
        self.app = app
        return app, rest, parse_qs(url.query)

    def do_OPTIONS(self) -> None:  # CORS-Preflight
        self._app()
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/gesundheit":
            self.antwort(200, {"ok": True})
            return
        app, rest, query = self._app()
        if not app:
            self.antwort(404, {"fehler": "nicht gefunden"})
            return
        app.get(self, rest, query)

    def do_POST(self) -> None:
        app, rest, _ = self._app()
        if not app:
            self.antwort(404, {"fehler": "nicht gefunden"})
            return
        app.post(self, rest)

    def log_message(self, fmt: str, *args) -> None:  # knappe Logs ohne Inhalte/Tokens
        print(f"{self.client_ip()} {fmt % args}".split("?")[0].split("#")[0], flush=True)


def erstelle_server(aufloesen: Aufloeser, port: int, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    klasse = type("KundenHandler", (Handler,), {"aufloesen": staticmethod(aufloesen)})
    return ThreadingHTTPServer((host, port), klasse)


def starten(konfig: KundenKonfig, port: int = 8080, host: str = "0.0.0.0") -> None:
    """Einzelbetrieb: ein Kunde direkt unter /."""
    app = KundenApp(konfig)
    server = erstelle_server(lambda pfad: (app, pfad.strip("/")), port, host)
    print(f"Agent-Server für {konfig.firma['name']} auf http://{host}:{port}  (Demo: /demo, Cockpit: /cockpit)")
    server.serve_forever()
