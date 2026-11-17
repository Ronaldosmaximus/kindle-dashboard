#!/usr/bin/env python3
"""Kindle-Dashboard (Paperwhite 10. Gen, 1072x1448): Wetter Wien + nächste 2 Lauftrainings aus Garmin Connect."""
import json
import math
import os
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar
from PIL import Image, ImageDraw, ImageFont

W, H = 1072, 1448
M = 60
TZ = ZoneInfo("Europe/Vienna")
LAT, LON, ORT = 48.2082, 16.3738, "Wien"
FONT_DIR = os.environ.get("FONT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"))
WOCHENTAG = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
WOCHENTAG_LANG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONAT = ["Jänner", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
         "September", "Oktober", "November", "Dezember"]


def font(size, weight="Regular"):
    for name in (f"Inter-{weight}.otf", f"Inter-{weight}.ttf", "Inter-Regular.otf"):
        p = os.path.join(FONT_DIR, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.truetype("DejaVuSans.ttf", size)


# ---------------------------------------------------------------- Daten
def wetter_laden():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT, "longitude": LON, "timezone": "Europe/Vienna",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,wind_speed_10m",
        "hourly": "temperature_2m,weather_code,precipitation_probability,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
        "forecast_days": 3,
    }
    for versuch in range(4):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if versuch == 3:
                raise
            time.sleep(15)


def trainings_laden(quelle, heute, anzahl=2):
    if quelle.startswith("http"):
        raw = requests.get(quelle, timeout=30).content
    else:
        with open(quelle, "rb") as f:
            raw = f.read()
    events = []
    for ev in Calendar.from_ical(raw).walk("VEVENT"):
        d = ev.decoded("DTSTART")
        if isinstance(d, datetime):
            d = d.astimezone(TZ).date()
        titel = str(ev.get("SUMMARY", "")).strip()
        if titel.upper().startswith("HM130"):
            titel = titel[5:].strip()
        if d >= heute:
            events.append((d, titel))
    events.sort()
    return events[:anzahl]


# ---------------------------------------------------------------- Wetter-Icons
WMO_TEXT = {
    0: "Klar", 1: "Überwiegend klar", 2: "Teils bewölkt", 3: "Bewölkt",
    45: "Nebel", 48: "Raureifnebel", 51: "Leichter Niesel", 53: "Niesel", 55: "Starker Niesel",
    56: "Gefrierender Niesel", 57: "Gefrierender Niesel", 61: "Leichter Regen", 63: "Regen",
    65: "Starker Regen", 66: "Gefrierender Regen", 67: "Gefrierender Regen", 71: "Leichter Schnee",
    73: "Schnee", 75: "Starker Schnee", 77: "Schneegriesel", 80: "Regenschauer", 81: "Regenschauer",
    82: "Heftige Schauer", 85: "Schneeschauer", 86: "Schneeschauer", 95: "Gewitter",
    96: "Gewitter mit Hagel", 99: "Gewitter mit Hagel",
}


def icon_art(code, tag=True):
    if code in (0, 1):
        return "sonne" if tag else "mond"
    if code == 2:
        return "teils" if tag else "teils_nacht"
    if code == 3:
        return "wolke"
    if code in (45, 48):
        return "nebel"
    if code in (71, 73, 75, 77, 85, 86):
        return "schnee"
    if code in (95, 96, 99):
        return "gewitter"
    return "regen"


def _sonne(d, cx, cy, r, w):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=w)
    for i in range(8):
        a = i * math.pi / 4
        d.line([cx + math.cos(a) * r * 1.4, cy + math.sin(a) * r * 1.4,
                cx + math.cos(a) * r * 1.85, cy + math.sin(a) * r * 1.85], fill=0, width=w)


def _mond(d, cx, cy, r, w, bg=255):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=w, fill=bg)
    o = r * 0.55
    d.ellipse([cx - r + o, cy - r - o * 0.4, cx + r + o, cy + r - o * 0.4], fill=bg)
    d.arc([cx - r + o, cy - r - o * 0.4, cx + r + o, cy + r - o * 0.4], 90, 200, fill=0, width=w)


def _wolke(d, x, y, s, w, fill=255):
    # Wolke in Box (x, y, x+s, y+0.62s)
    h = s * 0.62
    base = y + h
    parts = [
        (x, y + h * 0.42, x + s * 0.46, base),
        (x + s * 0.18, y + h * 0.12, x + s * 0.66, y + h * 0.88),
        (x + s * 0.48, y + h * 0.30, x + s, base),
    ]
    for p in parts:
        d.ellipse(p, fill=0)
    inset = w
    for p in parts:
        d.ellipse([p[0] + inset, p[1] + inset, p[2] - inset, p[3] - inset], fill=fill)
    d.rectangle([x + s * 0.23, y + h * 0.7, x + s * 0.74, base - inset], fill=fill)
    d.line([x + s * 0.23, base - w / 2, x + s * 0.74, base - w / 2], fill=0, width=w)


def wetter_icon(img, art, cx, cy, s):
    """Zeichnet Icon zentriert auf (cx, cy) mit Größe s."""
    d = ImageDraw.Draw(img)
    w = max(2, int(s / 22))
    if art == "sonne":
        _sonne(d, cx, cy, s * 0.24, w)
        return
    if art == "mond":
        _mond(d, cx, cy, s * 0.32, w)
        return
    if art in ("teils", "teils_nacht"):
        if art == "teils":
            _sonne(d, cx - s * 0.16, cy - s * 0.16, s * 0.17, w)
        else:
            _mond(d, cx - s * 0.12, cy - s * 0.16, s * 0.24, w)
        _wolke(d, cx - s * 0.4, cy - s * 0.08, s * 0.82, w)
        return
    top = cy - s * 0.36
    _wolke(d, cx - s * 0.45, top, s * 0.9, w)
    unten = top + s * 0.9 * 0.62 + s * 0.08
    if art == "regen":
        for i in range(3):
            x = cx - s * 0.2 + i * s * 0.2
            d.line([x, unten, x - s * 0.06, unten + s * 0.2], fill=0, width=w)
    elif art == "schnee":
        for i in range(3):
            x = cx - s * 0.2 + i * s * 0.2
            r = s * 0.035
            d.ellipse([x - r, unten + s * 0.08 - r, x + r, unten + s * 0.08 + r], fill=0)
    elif art == "gewitter":
        pts = [(cx + s * 0.03, unten - s * 0.02), (cx - s * 0.08, unten + s * 0.13),
               (cx + s * 0.02, unten + s * 0.13), (cx - s * 0.07, unten + s * 0.3)]
        d.line(pts, fill=0, width=w, joint="curve")
    elif art == "nebel":
        for i in range(2):
            y = unten + i * s * 0.11
            d.line([cx - s * 0.32, y, cx + s * 0.32, y], fill=0, width=w)


# ---------------------------------------------------------------- Layout-Helfer
def text_c(d, xy, txt, f, fill=0):
    d.text(xy, txt, font=f, fill=fill, anchor="mm")


def umbrechen(d, txt, f, breite):
    zeilen, akt = [], ""
    for wort in txt.split():
        test = (akt + " " + wort).strip()
        if d.textlength(test, font=f) <= breite:
            akt = test
        else:
            if akt:
                zeilen.append(akt)
            akt = wort
    if akt:
        zeilen.append(akt)
    return zeilen


def relativ(d, heute):
    diff = (d - heute).days
    return {0: "Heute", 1: "Morgen", 2: "Übermorgen"}.get(diff, f"in {diff} Tagen")


# ---------------------------------------------------------------- Rendern
def rendern(wetter, trainings, jetzt):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    heute = jetzt.date()

    # Kopfzeile
    d.text((M, 52), ORT, font=font(40, "SemiBold"), fill=0, anchor="lm")
    datum = f"{WOCHENTAG_LANG[heute.weekday()]}, {heute.day}. {MONAT[heute.month - 1]}"
    d.text((W / 2, 52), datum, font=font(32), fill=0, anchor="mm")
    d.text((W - M, 52), f"Stand {jetzt:%H:%M}", font=font(28), fill=90, anchor="rm")
    d.line([M, 95, W - M, 95], fill=0, width=3)

    cur, daily, hourly = wetter["current"], wetter["daily"], wetter["hourly"]

    # Aktuell (links)
    wetter_icon(img, icon_art(cur["weather_code"], cur.get("is_day", 1) == 1), 210, 250, 230)
    temp = f"{round(cur['temperature_2m'])}°"
    d.text((345, 250), temp, font=font(170, "SemiBold"), fill=0, anchor="lm")
    text_c(d, (290, 430), WMO_TEXT.get(cur["weather_code"], ""), font(40, "Medium"))
    text_c(d, (290, 480), f"Gefühlt {round(cur['apparent_temperature'])}° · Feuchte {cur['relative_humidity_2m']}%",
           font(28), fill=60)

    # Heute / Morgen (rechts)
    x0 = 660
    d.line([x0 - 30, 130, x0 - 30, 510], fill=170, width=2)
    d.text((x0, 140), "Heute", font=font(30), fill=80, anchor="lt")
    d.text((x0, 180), f"{round(daily['temperature_2m_max'][0])}° / {round(daily['temperature_2m_min'][0])}°",
           font=font(64, "SemiBold"), fill=0, anchor="lt")
    d.text((x0, 262), f"Regen {daily['precipitation_probability_max'][0]}% · {round(daily['wind_speed_10m_max'][0])} km/h",
           font=font(28), fill=40, anchor="lt")
    d.line([x0, 320, W - M, 320], fill=170, width=2)
    d.text((x0, 340), "Morgen", font=font(30), fill=80, anchor="lt")
    wetter_icon(img, icon_art(daily["weather_code"][1]), x0 + 45, 430, 90)
    d.text((x0 + 110, 405), f"{round(daily['temperature_2m_max'][1])}° / {round(daily['temperature_2m_min'][1])}°",
           font=font(48, "SemiBold"), fill=0, anchor="lm")
    d.text((x0 + 110, 458), f"{daily['precipitation_probability_max'][1]}% Regen", font=font(28), fill=40, anchor="lm")

    # Stundenvorschau: ab nächster voller Stunde, alle 2 h, 7 Spalten
    d.line([M, 540, W - M, 540], fill=0, width=2)
    zeiten = [datetime.fromisoformat(t).replace(tzinfo=TZ) for t in hourly["time"]]
    start = next((i for i, t in enumerate(zeiten) if t > jetzt), 0)
    idx = [start + 2 * k for k in range(7) if start + 2 * k < len(zeiten)]
    spalte = (W - 2 * M) / 7
    for k, i in enumerate(idx):
        cx = M + spalte * (k + 0.5)
        text_c(d, (cx, 580), f"{zeiten[i]:%H:%M}", font(26), fill=60)
        wetter_icon(img, icon_art(hourly["weather_code"][i], hourly["is_day"][i] == 1), cx, 655, 80)
        text_c(d, (cx, 730), f"{round(hourly['temperature_2m'][i])}°", font(36, "SemiBold"))
        text_c(d, (cx, 772), f"{hourly['precipitation_probability'][i]}%", font(24), fill=90)
    d.line([M, 810, W - M, 810], fill=0, width=3)

    # Nächste Trainings
    d.text((M, 860), "Nächste Lauftrainings", font=font(40, "SemiBold"), fill=0, anchor="lm")
    if not trainings:
        text_c(d, (W / 2, 1100), "Keine geplanten Trainings", font(40), fill=90)
    karte_h = 225
    for n, (tag, titel) in enumerate(trainings):
        y = 905 + n * (karte_h + 28)
        d.rounded_rectangle([M, y, W - M, y + karte_h], radius=22, outline=0, width=3)
        # Datumsblock (erster schwarz hinterlegt)
        bx0, bx1 = M + 24, M + 224
        dunkel = n == 0
        d.rounded_rectangle([bx0, y + 24, bx1, y + karte_h - 24], radius=16,
                            fill=0 if dunkel else 255, outline=0, width=3)
        fg = 255 if dunkel else 0
        bmid = (bx0 + bx1) / 2
        text_c(d, (bmid, y + 66), relativ(tag, heute), font(30, "Medium"), fill=fg)
        text_c(d, (bmid, y + 118), WOCHENTAG[tag.weekday()], font(56, "SemiBold"), fill=fg)
        text_c(d, (bmid, y + 168), f"{tag.day}.{tag.month}.", font(30), fill=fg)
        # Titel + Art
        tx = bx1 + 40
        breite = W - M - 30 - tx
        ft = font(58, "SemiBold")
        zeilen = umbrechen(d, titel, ft, breite)
        if len(zeilen) > 2:
            ft = font(46, "SemiBold")
            zeilen = umbrechen(d, titel, ft, breite)[:2]
        zh = ft.size + 12
        y0 = y + karte_h / 2 - len(zeilen) * zh / 2 + zh / 2
        for z, zeile in enumerate(zeilen):
            d.text((tx, y0 + z * zh), zeile, font=ft, fill=0, anchor="lm")

    return img


def main():
    jetzt = datetime.now(TZ)
    out = sys.argv[1] if len(sys.argv) > 1 else "dash.png"
    ics = os.environ.get("GARMIN_ICS_URL") or os.environ.get("GARMIN_ICS_FILE")
    mock = os.environ.get("WETTER_MOCK")
    if os.environ.get("JETZT"):
        jetzt = datetime.fromisoformat(os.environ["JETZT"]).replace(tzinfo=TZ)
    wetter = json.load(open(mock)) if mock else wetter_laden()
    trainings = trainings_laden(ics, jetzt.date()) if ics else []
    img = rendern(wetter, trainings, jetzt)
    img.save(out, optimize=True)
    print(f"gespeichert: {out}, Trainings: {trainings}")


if __name__ == "__main__":
    main()
