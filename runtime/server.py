"""HTTP-Server für Website-Chat, Webhooks (Formulare, Telefonie-Anbieter) und Kalender-Feed.

Endpunkte:
  GET  /widget.js                  Chat-Widget zum Einbinden auf der Kunden-Website
  POST /chat/<agent>               {"sitzung": "...", "nachricht": "..."} -> {"antwort": "..."}
  POST /webhook/<agent>            beliebiges JSON (z. B. Kontaktformular); Header X-Token erforderlich
  POST /vapi/<agent>               Telefon-Kanal: Werkzeugaufrufe + Anrufberichte von Vapi
                                   (Authorization: Bearer <Token> oder X-Vapi-Secret)
  GET  /kalender.ics?token=...     Termin-Feed zum Abonnieren in Google/Outlook
  GET  /gesundheit                 Healthcheck

Nur Standardbibliothek, damit es auf jedem kleinen Server läuft. Für Produktion hinter einen
Reverse-Proxy mit HTTPS (z. B. Caddy/nginx) stellen.
"""

from __future__ import annotations

import hmac
import json
import os
import threading
import time
from collections import OrderedDict, defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import KundenKonfig
from .engine import Agent, AgentFehler
from .telefon import vapi_nachricht
from .store import JsonStore
from .werkzeuge import Werkzeuge

STATIC = Path(__file__).parent / "static"
MAX_NACHRICHT = 2000
MAX_SITZUNGEN = 500
MAX_RUNDEN = 30
ANFRAGEN_PRO_MINUTE = 12


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


def starten(konfig: KundenKonfig, port: int = 8080, host: str = "0.0.0.0") -> None:
    srv_cfg = konfig.daten.get("server", {})
    erlaubte_origins = set(srv_cfg.get("erlaubte_origins", []))
    token = os.environ.get(srv_cfg.get("token_env", "AGENT_TOKEN"), "")
    agenten: dict[str, Agent] = {}
    sitzungen = Sitzungen()
    anfragen: defaultdict[str, deque] = defaultdict(deque)

    def agent_fuer(name: str, kanal: str) -> Agent | None:
        a = konfig.daten["agenten"].get(name)
        if not a or kanal not in a.get("kanaele", []):
            return None
        if name not in agenten:
            agenten[name] = Agent(konfig, name)
        return agenten[name]

    class Handler(BaseHTTPRequestHandler):
        server_version = "NGCustomsAgent/1.0"

        def _cors(self) -> None:
            origin = self.headers.get("Origin", "")
            if origin and (origin in erlaubte_origins or "*" in erlaubte_origins):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _antwort(self, code: int, inhalt: dict | str, typ: str = "application/json") -> None:
            body = (json.dumps(inhalt, ensure_ascii=False) if isinstance(inhalt, dict) else inhalt).encode()
            self.send_response(code)
            self.send_header("Content-Type", f"{typ}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _json_body(self) -> dict | None:
            laenge = int(self.headers.get("Content-Length", 0))
            if laenge > 100_000:
                return None
            try:
                return json.loads(self.rfile.read(laenge) or b"{}")
            except json.JSONDecodeError:
                return None

        def _limit_ueberschritten(self) -> bool:
            ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
            q, jetzt = anfragen[ip], time.time()
            while q and q[0] < jetzt - 60:
                q.popleft()
            q.append(jetzt)
            return len(q) > ANFRAGEN_PRO_MINUTE

        def _token_ok(self, wert: str) -> bool:
            return bool(token) and hmac.compare_digest(wert, token)

        def do_OPTIONS(self) -> None:  # CORS-Preflight
            self.send_response(204)
            self._cors()
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.end_headers()

        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path == "/gesundheit":
                self._antwort(200, {"ok": True, "firma": konfig.firma["name"]})
            elif url.path == "/widget.js":
                self._antwort(200, (STATIC / "widget.js").read_text(encoding="utf-8"), "application/javascript")
            elif url.path == "/demo":
                self._antwort(200, (STATIC / "demo.html").read_text(encoding="utf-8"), "text/html")
            elif url.path == "/kalender.ics":
                if not self._token_ok(parse_qs(url.query).get("token", [""])[0]):
                    self._antwort(403, {"fehler": "Token ungültig"})
                    return
                ics = Werkzeuge(konfig, JsonStore(konfig.daten_dir)).kalender_ics()
                self._antwort(200, ics, "text/calendar")
            else:
                self._antwort(404, {"fehler": "nicht gefunden"})

        def do_POST(self) -> None:
            teile = urlparse(self.path).path.strip("/").split("/")
            if len(teile) != 2 or teile[0] not in ("chat", "webhook", "vapi"):
                self._antwort(404, {"fehler": "nicht gefunden"})
                return
            art, name = teile
            if art == "vapi":
                self._vapi(name)
                return
            if self._limit_ueberschritten():
                self._antwort(429, {"fehler": "Zu viele Anfragen – bitte kurz warten."})
                return
            agent = agent_fuer(name, art)
            if not agent:
                self._antwort(404, {"fehler": f"Agent '{name}' ist für '{art}' nicht freigeschaltet"})
                return
            body = self._json_body()
            if body is None:
                self._antwort(400, {"fehler": "Ungültiges JSON"})
                return

            if art == "webhook":
                if not self._token_ok(self.headers.get("X-Token", "")):
                    self._antwort(403, {"fehler": "Token ungültig"})
                    return
                eingang = json.dumps(body, ensure_ascii=False, indent=2)[:20000]
                auftrag = ("Neuer Eingang über Webhook (z. B. Kontaktformular oder Telefon-Transkript). "
                           f"Bearbeite ihn vollständig gemäß deiner Rolle.\n\n<eingang>\n{eingang}\n</eingang>")
                try:
                    ergebnis, _ = agent.ausfuehren(auftrag, kanal="webhook")
                    self._antwort(200, {"ok": True, "aktionen": len(ergebnis.aktionen), "bericht": ergebnis.text})
                except Exception as e:
                    print(f"FEHLER (webhook): {type(e).__name__}: {e}")
                    self._antwort(502, {"fehler": str(e) if isinstance(e, AgentFehler) else "interner Fehler"})
                return

            nachricht = str(body.get("nachricht", "")).strip()[:MAX_NACHRICHT]
            sid = str(body.get("sitzung", ""))[:64]
            if not nachricht or not sid:
                self._antwort(400, {"fehler": "'sitzung' und 'nachricht' erforderlich"})
                return
            with sitzungen.sperre(sid):
                verlauf = sitzungen.holen(sid)
                if len(verlauf) > MAX_RUNDEN * 4:
                    self._antwort(200, {"antwort": "Dieses Gespräch ist sehr lang geworden. Bitte laden Sie die "
                                                   "Seite neu oder kontaktieren Sie uns direkt."})
                    return
                try:
                    ergebnis, verlauf = agent.ausfuehren(nachricht, verlauf, kanal="chat")
                    sitzungen.setzen(sid, verlauf)
                    self._antwort(200, {"antwort": ergebnis.text})
                except Exception as e:  # Besucher bekommt immer eine Antwort, Details nur ins Log
                    print(f"FEHLER: {type(e).__name__}: {e}")
                    tel = konfig.firma.get("telefon", "")
                    self._antwort(200, {"antwort": "Entschuldigung, gerade gibt es eine technische Störung. "
                                                   + (f"Sie erreichen uns telefonisch unter {tel}." if tel else "")})

        def _vapi(self, name: str) -> None:
            auth = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not self._token_ok(auth or self.headers.get("X-Vapi-Secret", "")):
                self._antwort(403, {"fehler": "Token ungültig"})
                return
            agent = agent_fuer(name, "telefon")
            body = self._json_body()
            if not agent or body is None:
                self._antwort(404 if not agent else 400, {"fehler": "Agent nicht für Telefon freigeschaltet"
                                                           if not agent else "Ungültiges JSON"})
                return
            try:
                self._antwort(200, vapi_nachricht(agent, body))
            except Exception as e:
                print(f"FEHLER (vapi): {type(e).__name__}: {e}")
                self._antwort(500, {"fehler": "interner Fehler"})

        def log_message(self, fmt: str, *args) -> None:  # knappe Logs ohne Nachrichteninhalte
            print(f"{self.address_string()} {fmt % args}")

    print(f"Agent-Server für {konfig.firma['name']} auf http://{host}:{port}  (Demo: /demo)")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
