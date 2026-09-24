/*
 * NG Customs Chat-Widget
 * Einbinden auf der Kunden-Website:
 *   <script src="https://agent.kunde.de/widget.js" data-agent="rezeption"
 *           data-titel="Digitale Rezeption" data-farbe="#1f6feb" defer></script>
 */
(function () {
  var skript = document.currentScript;
  var basis = new URL(skript.src).origin;
  var agent = skript.dataset.agent || "rezeption";
  var titel = skript.dataset.titel || "Digitale Rezeption";
  var farbe = skript.dataset.farbe || "#1f6feb";
  var datenschutz = skript.dataset.datenschutz || "";
  var sitzung;
  try {
    sitzung = sessionStorage.getItem("ngc-sitzung");
    if (!sitzung) {
      sitzung = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem("ngc-sitzung", sitzung);
    }
  } catch (e) {
    sitzung = Math.random().toString(36).slice(2);
  }

  var css =
    ".ngc-knopf{position:fixed;right:20px;bottom:20px;width:60px;height:60px;border-radius:50%;border:0;cursor:pointer;color:#fff;font-size:26px;box-shadow:0 4px 14px rgba(0,0,0,.25);z-index:99998}" +
    ".ngc-fenster{position:fixed;right:20px;bottom:90px;width:min(370px,calc(100vw - 32px));height:min(540px,calc(100vh - 120px));background:#fff;color:#1a1a1a;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.25);display:none;flex-direction:column;overflow:hidden;z-index:99999;font:15px/1.45 system-ui,sans-serif}" +
    ".ngc-kopf{padding:14px 16px;color:#fff;font-weight:600}.ngc-kopf small{display:block;font-weight:400;opacity:.9;font-size:12px}" +
    ".ngc-verlauf{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f6f7f9}" +
    ".ngc-msg{max-width:85%;padding:9px 12px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word}" +
    ".ngc-bot{background:#fff;border:1px solid #e3e5e8;align-self:flex-start}.ngc-ich{color:#fff;align-self:flex-end}" +
    ".ngc-form{display:flex;border-top:1px solid #e3e5e8}.ngc-form input{flex:1;border:0;padding:12px;font:inherit;outline:none}" +
    ".ngc-form button{border:0;background:none;padding:0 14px;cursor:pointer;font-weight:600}" +
    ".ngc-hinweis{font-size:11px;color:#666;padding:6px 12px;background:#fff}.ngc-hinweis a{color:inherit}";
  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  var knopf = document.createElement("button");
  knopf.className = "ngc-knopf";
  knopf.style.background = farbe;
  knopf.setAttribute("aria-label", "Chat öffnen");
  knopf.textContent = "💬";

  var fenster = document.createElement("div");
  fenster.className = "ngc-fenster";
  fenster.setAttribute("role", "dialog");
  fenster.innerHTML =
    '<div class="ngc-kopf"></div><div class="ngc-verlauf" aria-live="polite"></div>' +
    '<div class="ngc-hinweis"></div>' +
    '<form class="ngc-form"><input maxlength="2000" placeholder="Ihre Nachricht …" aria-label="Nachricht"><button type="submit">Senden</button></form>';
  var kopf = fenster.querySelector(".ngc-kopf");
  kopf.style.background = farbe;
  kopf.textContent = titel;
  var unter = document.createElement("small");
  unter.textContent = "KI-Assistent – antwortet automatisch";
  kopf.appendChild(unter);
  var hinweis = fenster.querySelector(".ngc-hinweis");
  hinweis.textContent = "Sie chatten mit einer KI. Bitte keine sensiblen Daten eingeben. ";
  if (datenschutz) {
    var link = document.createElement("a");
    link.href = datenschutz;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Datenschutz";
    hinweis.appendChild(link);
  }
  fenster.querySelector(".ngc-form button").style.color = farbe;
  var verlauf = fenster.querySelector(".ngc-verlauf");
  var form = fenster.querySelector("form");
  var feld = form.querySelector("input");

  function nachricht(text, vonMir) {
    var el = document.createElement("div");
    el.className = "ngc-msg " + (vonMir ? "ngc-ich" : "ngc-bot");
    if (vonMir) el.style.background = farbe;
    el.textContent = text;
    verlauf.appendChild(el);
    verlauf.scrollTop = verlauf.scrollHeight;
    return el;
  }

  var begruesst = false;
  knopf.onclick = function () {
    var offen = fenster.style.display === "flex";
    fenster.style.display = offen ? "none" : "flex";
    if (!offen) {
      if (!begruesst) {
        nachricht("Guten Tag! Ich bin der digitale Assistent. Wie kann ich Ihnen helfen?", false);
        begruesst = true;
      }
      feld.focus();
    }
  };

  form.onsubmit = function (e) {
    e.preventDefault();
    var text = feld.value.trim();
    if (!text) return;
    feld.value = "";
    nachricht(text, true);
    var warte = nachricht("…", false);
    feld.disabled = true;
    fetch(basis + "/chat/" + encodeURIComponent(agent), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sitzung: sitzung, nachricht: text }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) { warte.textContent = d.antwort || d.fehler || "Keine Antwort erhalten."; })
      .catch(function () { warte.textContent = "Verbindung fehlgeschlagen. Bitte versuchen Sie es später erneut."; })
      .finally(function () { feld.disabled = false; feld.focus(); verlauf.scrollTop = verlauf.scrollHeight; });
  };

  document.body.appendChild(knopf);
  document.body.appendChild(fenster);
})();
