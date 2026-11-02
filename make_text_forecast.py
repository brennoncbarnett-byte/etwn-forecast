#!/usr/bin/env python3
import sys
import textwrap
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

# Match your existing repo
STATION = "EAST TENNESSEE WEATHER NETWORK"
CITY = "JOHNSON CITY, TN"
LAT, LON = 36.3134, -82.3535
TZ = "America/New_York"
CONTACT = "ETWN forecast graphic (your-email@example.com)"
OUTPUT = "text_forecast.png"

W, H = 1920, 1080
NAVY = (5, 18, 52)
GOLD = (255, 200, 40)
WHITE = (255, 255, 255)
LT = (190, 215, 245)

def font(bold, size):
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/Library/Fonts/Arial Bold.ttf",
         "C:/Windows/Fonts/arialbd.ttf"]
        if bold
        else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/Library/Fonts/Arial.ttf",
         "C:/Windows/Fonts/arial.ttf"]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()

def get_json(url, headers, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"Could not reach the weather service: {last}")

def fetch_periods():
    headers = {"User-Agent": CONTACT, "Accept": "application/geo+json"}
    point = get_json(f"https://api.weather.gov/points/{LAT},{LON}", headers)
    forecast = get_json(point["properties"]["forecast"], headers)
    return forecast["properties"]["periods"]

def build_days(periods, today):
    days = {}
    for p in periods:
        start = datetime.fromisoformat(p["startTime"])
        key = start.date()
        if not p["isDaytime"] and start.hour < 12:
            key -= timedelta(days=1)
        d = days.setdefault(key, {"date": key, "hi": None, "lo": None, "desc": None, "rain": 0})
        pop = (p.get("probabilityOfPrecipitation") or {}).get("value") or 0
        d["rain"] = max(d["rain"], pop)
        if p["isDaytime"]:
            d["hi"], d["desc"] = p["temperature"], p["shortForecast"]
        else:
            d["lo"] = p["temperature"]
            d["desc"] = d["desc"] or p["shortForecast"]
    keys = [k for k in sorted(days) if k >= today]
    return [days[k] for k in keys][:7]

def draw_text_graphic(days, now):
    img = Image.new("RGB", (W, H), color=(244, 247, 250))
    d = ImageDraw.Draw(img)

    # Header band
    d.rectangle([0, 0, W, 150], fill=NAVY)
    d.rectangle([0, 150, W, 158], fill=GOLD)
    d.polygon([(0, 0), (560, 0), (500, 150), (0, 150)], fill=GOLD)

    d.text((50, 28), "TEXT", font=font(True, 62), fill=NAVY)
    d.text((50, 92), "FORECAST", font=font(True, 44), fill=NAVY)
    d.text((620, 12), STATION, font=font(True, 30), fill=GOLD)
    d.text((620, 48), CITY, font=font(True, 58), fill=WHITE)
    d.text((620, 106), now.strftime("%A, %B %-d, %Y") if sys.platform != "win32" else now.strftime("%A, %B %d, %Y"),
           font=font(False, 30), fill=LT)

    # Body area
    box_x = 80
    box_y = 220
    box_w = W - 160
    box_h = H - 320
    d.rounded_rectangle([box_x, box_y, box_x + box_w, box_y + box_h], radius=24, fill=(15, 44, 108), outline=GOLD, width=4)

    # Subtitle
    d.text((box_x + 30, box_y + 28), "NATIONAL WEATHER SERVICE FORECAST DISCUSSION", font=font(True, 30), fill=GOLD)

    line_y = box_y + 90
    for i, day in enumerate(days[:5]):
        start_x = box_x + 30
        start_y = line_y + i * 135

        # Date
        date_label = day["date"].strftime("%a %b %-d") if sys.platform != "win32" else day["date"].strftime("%a %b %d")
        d.text((start_x, start_y), date_label.upper(), font=font(True, 28), fill=WHITE)

        # High/Low
        hi = f"{day['hi']}°" if day["hi"] is not None else "--"
        lo = f"{day['lo']}°" if day["lo"] is not None else "--"
        d.text((start_x + 210, start_y), f"HI {hi}", font=font(True, 28), fill=LT)
        d.text((start_x + 430, start_y), f"LO {lo}", font=font(True, 28), fill=LT)

        # Rain chance
        rain = f"{int(day['rain'])}% RAIN"
        d.text((start_x + 620, start_y), rain, font=font(True, 28), fill=GOLD)

        # Description
        desc = (day["desc"] or "").strip()
        wrapped = textwrap.wrap(desc, width=55)
        desc_lines = wrapped[:2]
        for j, line in enumerate(desc_lines):
            d.text((start_x, start_y + 42 + j * 28), line, font=font(False, 24), fill=WHITE)

        # Divider line
        if i < 4:
            d.line([(start_x, start_y + 100), (box_x + box_w - 30, start_y + 100)], fill=(60, 110, 190), width=2)

    # Footer strip
    footer_y = H - 78
    d.rectangle([0, footer_y, W, H], fill=NAVY)
    d.text((W/2, H - 42), f"{STATION.title()} · Updated {now.strftime('%-I:%M %p %Z')} · Source: NWS",
           font=font(False, 22), fill=LT, anchor="mm")

    return img

def main():
    now = datetime.now(ZoneInfo(TZ))
    periods = fetch_periods()
    days = build_days(periods, now.date())
    if not days:
        raise SystemExit("No forecast data returned")
    img = draw_text_graphic(days, now)
    img.save(OUTPUT)
    print(f"Saved {OUTPUT}")

if __name__ == "__main__":
    main()
