# Kindle-Dashboard

E-Ink-Dashboard für den Kindle Paperwhite (10. Gen, 1072×1448): Wetter Wien (Open-Meteo) und die nächsten zwei Lauftrainings aus dem Garmin-Connect-Kalender.

- `render.py` erzeugt `dash.png`
- `.github/workflows/dashboard.yml` läuft alle 30 Minuten und veröffentlicht das Bild auf GitHub Pages
- Secret `GARMIN_ICS_URL`: veröffentlichter Garmin-Connect-Kalender-Link
