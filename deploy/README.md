# Plattform live schalten (einmalig, ca. 20 Minuten)

Danach ist **jeder Kunde, den der Autopilot baut, automatisch online**: Autopilot committet →
Server holt die Änderung (alle 5 Minuten) → Plattform lädt den Kunden neu. Kein Neustart, kein
Kopieren.

## Was du brauchst
1. **Server:** z. B. Hetzner Cloud CX22 (Ubuntu 24.04, ca. 5 €/Monat). Reicht für viele Kunden.
2. **Domain/Subdomain:** z. B. `agents.ng-customs.de` → DNS-**A-Eintrag** auf die IP des Servers.
3. **Claude-API-Key** von console.anthropic.com.

## Einrichtung
```bash
ssh root@<server-ip>
# Skript aus dem Repo holen (Datei deploy/einrichten.sh, z. B. im GitHub-Web öffnen → "Raw" → kopieren)
nano einrichten.sh      # Inhalt einfügen, speichern
bash einrichten.sh
```
Das Skript fragt nach Repo-Adresse, Deploy-Key (zeigt ihn an, du trägst ihn bei GitHub ein),
Branch, Domain und Claude-Key. Den Rest (Docker, HTTPS, Autostart, Auto-Update) erledigt es selbst.

Am Ende zeigt es `NGC_GEHEIMNIS` an. **Diesen Wert und `NGC_BASIS_URL` auch in der Claude-Code-Umgebung
als Umgebungsvariablen eintragen.** Dann erzeugt der Autopilot funktionierende Demo- und Cockpit-Links.

## Betrieb
| Aufgabe | Befehl (auf dem Server) |
|---|---|
| Logs ansehen | `cd /opt/ng-customs/deploy && docker compose logs -f plattform` |
| Sofort aktualisieren | `bash /opt/ng-customs/deploy/aktualisieren.sh` |
| Neustart | `cd /opt/ng-customs/deploy && docker compose restart` |
| E-Mail-Zugang eines Kunden | Variablen in `deploy/.env` ergänzen → `docker compose up -d` |
| Backup der Kundendaten | `tar czf backup.tgz /opt/ng-customs/kunden/*/daten` |

Kundendaten (Leads, Termine, Freigaben) liegen nur auf dem Server in `kunden/<slug>/daten/`,
nie in Git.
