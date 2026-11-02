#!/usr/bin/env python3
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

STATION = "EAST TENNESSEE WEATHER NETWORK"
CITY = "JOHNSON CITY, TN"
LAT, LON = 36.3134, -82.3535
TZ = "America/New_York"
CONTACT = "ETWN forecast graphic (your-email@example.com)"
OUTPUT = "overlay.png"

W, H = 1920, 1080
NAVY = (5, 18, 52)
GOLD = (255, 200, 40)
WHITE = (255, 255, 255)
LT = (190, 215, 245)
SEMI = (255, 255, 255, 180)


def font(bold, size):
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def get_json(url, headers, tries=4):
    last = None
    for attempt in range(tries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # pragma: no cover - network error path
            last = exc
            if attempt < tries - 1:
                import time
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Could not reach NOAA: {last}")


def fetch_periods():
    headers = {"User-Agent": CONTACT, "Accept": "application/geo+json"}
    point = get_json(f"https://api.weather.gov/points/{LAT},{LON}", headers)
    forecast = get_json(point["properties"]["forecast"], headers)
    return forecast["properties"]["periods"]


def parse_iso(value):
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def get_current_period(periods):
    now = datetime.now(ZoneInfo(TZ))
    for period in periods:
        try:
            start = parse_iso(period["startTime"])
            end = parse_iso(period["endTime"])
            if start <= now <= end:
                return period
        except Exception:
            continue
    return periods[0]


def get_day_and_night(periods):
    today = None
    hi = None
    lo = None
    for period in periods:
        if period.get("isDaytime"):
            value = period.get("temperature")
            if value is not None:
                hi = value
                today = period
                break
    for period in periods:
        if not period.get("isDaytime"):
            value = period.get("temperature")
            if value is not None:
                lo = value
                break
    return hi, lo, today


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def draw_weather_icon(draw, x, y, size, condition):
    cx = x + size // 2
    cy = y + size // 2
    draw.ellipse((x, y, x + size, y + size), fill=(255, 255, 255, 0), outline=(255, 255, 255, 220), width=4)

    cloud_color = (214, 229, 240)
    cloud = [(cx - 22, cy + 10), (cx - 14, cy - 6), (cx, cy - 12), (cx + 18, cy - 5), (cx + 30, cy + 8), (cx + 24, cy + 18), (cx - 8, cy + 18)]
    draw.polygon(cloud, fill=cloud_color)

    if "sun" in condition.lower() or "clear" in condition.lower():
        draw.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=(255, 200, 40), outline=(255, 200, 40), width=2)
    else:
        draw.arc((cx - 16, cy - 18, cx + 16, cy + 10), 0, 180, fill=(255, 200, 40), width=4)


def build_overlay(periods):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    bar_h = 180
    bar_y = H - bar_h
    draw.rectangle([(0, bar_y), (W, H)], fill=(5, 18, 52, 255))
    draw.line([(0, bar_y), (W, bar_y)], fill=GOLD, width=4)

    logo_x, logo_y = 70, bar_y + 28
    logo_size = 110
    draw.rounded_rectangle((logo_x, logo_y, logo_x + logo_size, logo_y + logo_size), radius=18, fill=(8, 40, 92, 255), outline=GOLD, width=4)
    draw_weather_icon(draw, logo_x + 8, logo_y + 8, logo_size - 16, "Mostly Cloudy")

    label_font = font(True, 24)
    city_font = font(True, 58)
    condition_font = font(False, 34)
    value_font = font(True, 84)
    small_font = font(True, 22)
    metric_font = font(True, 28)

    draw.text((205, bar_y + 25), STATION, font=label_font, fill=(242, 244, 248))
    draw.text((205, bar_y + 58), CITY, font=city_font, fill=WHITE)

    current = get_current_period(periods)
    condition = current.get("shortForecast", "Mostly Cloudy")
    current_temp = current.get("temperature")
    hi, lo, _ = get_day_and_night(periods)
    precip = current.get("probabilityOfPrecipitation") or {}
    rain_value = precip.get("value")
    if rain_value is None:
        rain_value = 0
    rain_value = max(0, int(rain_value))

    draw.text((205, bar_y + 125), condition, font=condition_font, fill=(218, 232, 240))

    col_x = [850, 1030, 1210, 1425]
    labels = ["NOW", "HIGH", "LOW", "RAIN"]
    values = [
        f"{current_temp if current_temp is not None else '--'}°",
        f"{hi if hi is not None else '--'}°",
        f"{lo if lo is not None else '--'}°",
        f"{rain_value}%",
    ]

    for idx, label in enumerate(labels):
        x = col_x[idx]
        draw.text((x, bar_y + 26), label, font=small_font, fill=(214, 224, 240))
        draw.text((x, bar_y + 58), values[idx], font=value_font if idx == 0 else metric_font, fill=WHITE)

    return img


def main():
    periods = fetch_periods()
    if not periods:
        raise SystemExit("No forecast periods found")
    image = build_overlay(periods)
    image.save(OUTPUT)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
