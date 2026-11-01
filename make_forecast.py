#!/usr/bin/env python3
"""East Tennessee Weather Network - auto-updating 7-day forecast graphic.

Pulls the free National Weather Service forecast and draws a 1920x1080 PNG.
Run:   python make_forecast.py          (live data)
Test:  python make_forecast.py --demo   (fake data, no internet needed)
"""
import sys
import math
import time
import textwrap
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

# ---------------- SETTINGS (edit these) ----------------
STATION = "EAST TENNESSEE WEATHER NETWORK"
CITY = "JOHNSON CITY, TN"
LAT, LON = 36.3134, -82.3535
TZ = "America/New_York"
LOGO = "logo.png"
OUTPUT = "forecast.png"
OVERLAY_OUTPUT = "overlay.png"   # see-through lower-third for streaming
# The weather service asks for a contact in the User-Agent. Put your email here.
CONTACT = "ETWN forecast graphic (your-email@example.com)"
# -------------------------------------------------------

W, H = 1920, 1080
WH, GOLD, LT = (255, 255, 255), (255, 200, 40), (190, 215, 245)
NAVY = (5, 18, 52)


def font(bold, size):
    names = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/Library/Fonts/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------- DATA ----------------
def get_json(url, headers, tries=4):
    import requests
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # network hiccup or API busy: wait and retry
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"Could not reach the weather service: {last}")


def fetch_periods():
    h = {"User-Agent": CONTACT, "Accept": "application/geo+json"}
    point = get_json(f"https://api.weather.gov/points/{LAT},{LON}", h)
    forecast = get_json(point["properties"]["forecast"], h)
    return forecast["properties"]["periods"]


def fetch_current():
    """Latest observed temperature from the nearest station. Returns None if unavailable."""
    try:
        h = {"User-Agent": CONTACT, "Accept": "application/geo+json"}
        point = get_json(f"https://api.weather.gov/points/{LAT},{LON}", h, tries=2)
        stations = get_json(point["properties"]["observationStations"], h, tries=2)
        for st in stations["features"][:3]:
            sid = st["properties"]["stationIdentifier"]
            obs = get_json(f"https://api.weather.gov/stations/{sid}/observations/latest", h, tries=2)["properties"]
            c = (obs.get("temperature") or {}).get("value")
            if c is not None:
                return {"temp": round(c * 9 / 5 + 32), "text": obs.get("textDescription")}
    except Exception:
        return None
    return None


def demo_periods():
    now = datetime.now(ZoneInfo(TZ)).replace(minute=0, second=0, microsecond=0)
    texts = ["Mostly Cloudy", "Partly Sunny", "Chance Showers And Thunderstorms",
             "Showers Likely", "Sunny", "Mostly Sunny", "Slight Chance Rain Showers"]
    out = []
    for i in range(7):
        day = (now + timedelta(days=i)).replace(hour=7)
        out.append({"startTime": day.isoformat(), "isDaytime": True,
                    "temperature": 66 + i, "shortForecast": texts[i],
                    "probabilityOfPrecipitation": {"value": [20, 10, 60, 70, 0, 5, 30][i]}})
        night = day.replace(hour=19)
        out.append({"startTime": night.isoformat(), "isDaytime": False,
                    "temperature": 48 + i, "shortForecast": "Mostly Clear",
                    "probabilityOfPrecipitation": {"value": None}})
    return out


def build_days(periods, today):
    days = {}
    for p in periods:
        start = datetime.fromisoformat(p["startTime"])
        key = start.date()
        if not p["isDaytime"] and start.hour < 12:
            key -= timedelta(days=1)  # after-midnight hours belong to the evening before
        d = days.setdefault(key, {"date": key, "hi": None, "lo": None,
                                  "desc": None, "rain": 0})
        pop = (p.get("probabilityOfPrecipitation") or {}).get("value") or 0
        d["rain"] = max(d["rain"], pop)
        if p["isDaytime"]:
            d["hi"], d["desc"] = p["temperature"], p["shortForecast"]
        else:
            d["lo"] = p["temperature"]
            d["desc"] = d["desc"] or p["shortForecast"]
    keys = [k for k in sorted(days) if k >= today]
    return [days[k] for k in keys][:7]


def icon_kind(text):
    t = (text or "").lower()
    if "thunder" in t:
        return "storm"
    if any(w in t for w in ("snow", "flurr", "sleet", "wintry")):
        return "snow"
    if any(w in t for w in ("rain", "shower", "drizzle")):
        return "rain"
    if "partly" in t or "mostly sunny" in t or "mostly clear" in t:
        return "part"
    if any(w in t for w in ("cloud", "overcast", "fog", "haze")):
        return "cloud"
    if "sunny" in t or "clear" in t:
        return "sun"
    return "part"


# ---------------- DRAWING ----------------
def _cloud(d, x, y, s, col):
    for dx, dy, rx, ry in [(-30, 4, 38, 26), (8, -12, 46, 34), (40, 8, 38, 26), (0, 14, 64, 22)]:
        d.ellipse([x + (dx - rx) * s, y + (dy - ry) * s, x + (dx + rx) * s, y + (dy + ry) * s], fill=col)


def _sun(d, x, y, r):
    for a in range(0, 360, 30):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        d.line([(x + (r + 10) * ca, y + (r + 10) * sa), (x + (r + 26) * ca, y + (r + 26) * sa)], fill=GOLD, width=7)
    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 214, 70))


def _icon(d, k, x, y):
    cl, gr, dk = (238, 243, 250), (176, 188, 205), (120, 132, 152)
    if k == "sun":
        _sun(d, x, y, 36)
    elif k == "part":
        _sun(d, x - 22, y - 22, 28)
        _cloud(d, x + 12, y + 18, 1.0, cl)
    elif k == "cloud":
        _cloud(d, x, y, 1.2, gr)
    elif k == "rain":
        _cloud(d, x, y - 14, 1.1, gr)
        for dx in (-34, 0, 34):
            d.line([(x + dx + 4, y + 34), (x + dx - 8, y + 68)], fill=(110, 190, 255), width=8)
    elif k == "storm":
        _cloud(d, x, y - 14, 1.1, dk)
        d.polygon([(x + 6, y + 22), (x - 14, y + 52), (x - 2, y + 52), (x - 10, y + 80), (x + 20, y + 44), (x + 6, y + 44), (x + 16, y + 22)], fill=GOLD)
    elif k == "snow":
        _cloud(d, x, y - 14, 1.1, gr)
        for dx, dy in [(-34, 44), (0, 56), (34, 44), (-17, 72), (17, 72)]:
            d.ellipse([x + dx - 6, y + dy - 6, x + dx + 6, y + dy + 6], fill=WH)


def draw_graphic(days, now):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    top, bot = (18, 70, 150), (6, 24, 70)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.polygon([(0, 0), (900, 0), (300, H), (0, H)], fill=(255, 255, 255, 14))
    od.polygon([(1300, 0), (W, 0), (W, H), (900, H)], fill=(255, 255, 255, 10))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(img)

    # header
    d.rectangle([0, 0, W, 150], fill=NAVY)
    d.rectangle([0, 150, W, 158], fill=GOLD)
    d.polygon([(0, 0), (560, 0), (500, 150), (0, 150)], fill=GOLD)
    d.text((50, 28), "7-DAY", font=font(True, 62), fill=NAVY)
    d.text((50, 92), "FORECAST", font=font(True, 44), fill=NAVY)
    d.text((620, 12), STATION, font=font(True, 30), fill=GOLD)
    d.text((620, 48), CITY, font=font(True, 58), fill=WH)
    d.text((620, 106), now.strftime("%A, %B %-d, %Y") if sys.platform != "win32"
           else now.strftime("%A, %B %d, %Y"), font=font(False, 30), fill=LT)
    try:
        lg = Image.open(LOGO).convert("RGB").resize((124, 124), Image.LANCZOS)
        d.rounded_rectangle([W - 184, 8, W - 50, 142], radius=18, fill=WH)
        img.paste(lg, (W - 179, 13))
    except FileNotFoundError:
        pass

    icon = lambda k, x, y: _icon(d, k, x, y)

    m, gap = 40, 14
    cw = (W - 2 * m - 6 * gap) // 7
    y0, ch = 205, 690
    n = len(days)
    for i, day in enumerate(days):
        x = m + i * (cw + gap)
        first = i == 0
        d.rounded_rectangle([x, y0, x + cw, y0 + ch], radius=14,
                            fill=(14, 52, 128) if first else (10, 38, 100),
                            outline=GOLD if first else (60, 110, 190), width=4 if first else 2)
        hdr = GOLD if first else (28, 86, 176)
        d.rounded_rectangle([x, y0, x + cw, y0 + 86], radius=14, fill=hdr)
        d.rectangle([x, y0 + 60, x + cw, y0 + 86], fill=hdr)
        tc = NAVY if first else WH
        label = day["date"].strftime("%a").upper()
        if first and day["hi"] is None:
            label = "TONIGHT"
        d.text((x + cw / 2, y0 + 30), label, font=font(True, 44 if label != "TONIGHT" else 34), fill=tc, anchor="mm")
        d.text((x + cw / 2, y0 + 66), f"{day['date'].month}/{day['date'].day}", font=font(False, 24), fill=tc, anchor="mm")
        icon(icon_kind(day["desc"]), x + cw / 2, y0 + 215)

        lines = textwrap.wrap(day["desc"] or "", width=17)[:2]
        if len(textwrap.wrap(day["desc"] or "", width=17)) > 2:
            lines[-1] = lines[-1].rstrip(".") + "…"
        base = y0 + 345 - (14 if len(lines) == 2 else 0)
        for j, ln in enumerate(lines):
            d.text((x + cw / 2, base + j * 30), ln, font=font(True, 22), fill=WH, anchor="mm")

        hi = f"{day['hi']}°" if day["hi"] is not None else "--"
        lo = f"{day['lo']}°" if day["lo"] is not None else "--"
        d.text((x + cw / 2, y0 + 450), hi, font=font(True, 92), fill=WH, anchor="mm")
        d.text((x + cw / 2, y0 + 530), "HIGH", font=font(True, 20), fill=GOLD, anchor="mm")
        d.text((x + cw / 2, y0 + 585), lo, font=font(True, 52), fill=LT, anchor="mm")
        d.text((x + cw / 2, y0 + 630), "LOW", font=font(True, 20), fill=GOLD, anchor="mm")

    sy = y0 + ch + 22
    d.rectangle([0, sy, W, sy + 70], fill=NAVY)
    d.rectangle([0, sy, W, sy + 5], fill=GOLD)
    for i, day in enumerate(days):
        x = m + i * (cw + gap)
        col = (130, 200, 255) if day["rain"] >= 40 else WH
        d.text((x + cw / 2, sy + 38), f"{int(day['rain'])}% RAIN", font=font(True, 30), fill=col, anchor="mm")

    stamp = now.strftime("%-I:%M %p %Z") if sys.platform != "win32" else now.strftime("%I:%M %p %Z")
    d.text((W / 2, H - 22), f"{STATION.title()} · Updated {stamp} · Source: National Weather Service",
           font=font(False, 22), fill=LT, anchor="mm")
    return img


def draw_overlay(days, now, current):
    """Transparent 1920x1080 PNG with a lower-third bar. Layer it over your video."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, x1, y0, y1 = 60, W - 60, H - 210, H - 60
    d.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=NAVY + (235,))
    d.rounded_rectangle([x0, y0, x0 + 170, y1], radius=18, fill=GOLD)
    d.rectangle([x0 + 100, y0, x0 + 170, y1], fill=GOLD)
    try:
        lg = Image.open(LOGO).convert("RGB").resize((118, 118), Image.LANCZOS)
        d.rounded_rectangle([x0 + 26, y0 + 16, x0 + 144, y0 + 134], radius=14, fill=WH)
        img.paste(lg, (x0 + 26, y0 + 16))
    except FileNotFoundError:
        pass

    today = days[0]
    tx = x0 + 200
    d.text((tx, y0 + 18), STATION, font=font(True, 20), fill=GOLD)
    d.text((tx, y0 + 46), CITY, font=font(True, 44), fill=WH)
    desc = today["desc"] or ""
    if len(desc) > 30:
        desc = desc[:29].rstrip() + "…"
    d.text((tx, y0 + 102), desc, font=font(False, 28), fill=LT)

    tmp = Image.new("RGBA", (260, 220), (0, 0, 0, 0))
    _icon(ImageDraw.Draw(tmp), icon_kind(today["desc"]), 130, 110)
    tmp = tmp.resize((156, 132), Image.LANCZOS)
    img.paste(tmp, (850, y0 + 9), tmp)

    def block(cx, label, value, size=64):
        d.text((cx, y0 + 38), label, font=font(True, 20), fill=GOLD, anchor="mm")
        d.text((cx, y0 + 92), value, font=font(True, size), fill=WH, anchor="mm")

    cols = []
    if current:
        cols.append(("NOW", f"{current['temp']}°"))
    cols.append(("HIGH", f"{today['hi']}°" if today["hi"] is not None else "--"))
    cols.append(("LOW", f"{today['lo']}°" if today["lo"] is not None else "--"))
    cols.append(("RAIN", f"{int(today['rain'])}%"))
    start, step = 1060, 190
    for i, (lab, val) in enumerate(cols):
        cx = start + i * step + 60
        if i:
            d.line([(cx - step / 2, y0 + 25), (cx - step / 2, y1 - 25)], fill=(60, 110, 190, 255), width=2)
        block(cx, lab, val, 72 if lab == "NOW" else 64)
    return img


def main():
    now = datetime.now(ZoneInfo(TZ))
    periods = demo_periods() if "--demo" in sys.argv else fetch_periods()
    days = build_days(periods, now.date())
    if not days:
        raise SystemExit("No forecast days came back; leaving the old image in place.")
    current = {"temp": 64, "text": "Cloudy"} if "--demo" in sys.argv else fetch_current()
    draw_graphic(days, now).save(OUTPUT)
    draw_overlay(days, now, current).save(OVERLAY_OUTPUT)
    print(f"Saved {OUTPUT} and {OVERLAY_OUTPUT} with {len(days)} days.")


if __name__ == "__main__":
    main()
