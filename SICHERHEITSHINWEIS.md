# ⚠️ Sicherheitshinweis zur hochgeladenen `claude-agent-builder-main.zip`

Die ursprünglich hochgeladene Datei `claude-agent-builder-main.zip` (Kopie des GitHub-Repos
`jorgec020585/claude-agent-builder`) wurde aus dem Repository **entfernt**, weil sie
typische Merkmale einer Malware-Verteilung trägt:

- Sie enthält `examples/builder_agent_claude_v1.8-beta.2.zip` mit
  `Application.cmd` → `start unit.exe package.txt`, also eine unbekannte Windows-EXE, die eine
  verschleierte Nutzlast (`package.txt`, ~300 KB) lädt.
- Das README bewirbt diese ZIP mehrfach als „Windows-Installer“, obwohl ein Claude-Code-Skill
  nur aus Markdown-Dateien besteht und nie eine `.exe` braucht. Das ist ein bekanntes Muster
  gefälschter GitHub-Repos, die Info-Stealer verbreiten (Passwörter, Browser-Cookies, Krypto-Wallets).

**Falls du `unit.exe` / `Application.cmd` auf einem Windows-Rechner geöffnet hast:**
1. Rechner vom Netz trennen und mit Microsoft Defender (Offline-Scan) oder einem anderen
   aktuellen Virenscanner prüfen.
2. Von einem **anderen, sauberen Gerät** aus alle Passwörter ändern (E-Mail, GitHub, Banking,
   Anthropic/Claude, Hosting, Kunden-Zugänge) und überall Zwei-Faktor-Authentifizierung aktivieren.
3. Aktive Sitzungen abmelden (Google, Microsoft, GitHub → „Sitzungen“), API-Schlüssel rotieren.
4. Im Zweifel den Rechner neu aufsetzen.

Die Datei ist weiterhin in der Git-Historie (Commit `069f58e`) enthalten. Wer sie dauerhaft
entfernen möchte, kann die Historie bereinigen (z. B. mit `git filter-repo`) – das schreibt die
Historie um und sollte bewusst entschieden werden.

Die Markdown-Anleitung aus dem Paket (`agent-builder/SKILL.md`) war harmlos; ihre Ideen
(Analyse → Architektur → Freigabe → Bau → Prüfung) sind in die NG-Customs-Pipeline eingeflossen,
der Code in diesem Repository ist jedoch komplett neu geschrieben.
