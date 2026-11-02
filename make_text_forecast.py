#!/usr/bin/env python3
import argparse
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

CONTACT = "ETWN forecast graphic (your-email@example.com)"
LAT, LON = 36.3134, -82.3535
OUTPUT = "text_forecast.png"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
    "/System/Library/Fonts/Monaco.ttf",
    "/Library/Fonts/Courier.ttc",
]

def get_font(size):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def fetch_json(url, headers):
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def get_forecast():
    headers = {"User-Agent": CONTACT, "Accept": "application/geo+json"}
    point = fetch_json(f"https://api.weather.gov/points/{LAT},{LON}", headers)
    props = point["properties"]
    city = props.get("relativeLocation", {}).get("properties", {}).get("city", "Unknown City")
    state = props.get("relativeLocation", {}).get("properties", {}).get("state", "Unknown State")
    forecast = fetch_json(props["forecast"], headers)
    periods = forecast["properties"]["periods"]
    return city, state, periods

def draw_text_forecast(city, state, periods, output_path):
    W, H = 1200, 1600
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    margin_x = 70
    margin_y = 60
    y = margin_y

    title_font = get_font(34)
    head_font = get_font(26)
    body_font = get_font(24)
    small_font = get_font(18)

    d.text((margin_x, y), "NATIONAL WEATHER SERVICE", fill="black", font=title_font)
    y += 42
    d.text((margin_x, y), "FORECAST DISCUSSION", fill="black", font=head_font)
    y += 36
    d.text((margin_x, y), f"{city}, {state}", fill="#333333", font=head_font)
    y += 30

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    d.text((margin_x, y), f"Updated: {updated}", fill="#333333", font=small_font)
    y += 24
    d.line([(margin_x, y), (W - margin_x, y)], fill="#555555", width=2)
    y += 24

    for period in periods[:6]:
        name = period.get("name", "Forecast")
        temp = period.get("temperature")
        temp_unit = period.get("temperatureUnit", "F")
        short = period.get("shortForecast", "No forecast available")
        detailed = period.get("detailedForecast", short)

        d.text((margin_x, y), f"{name}: {temp}°{temp_unit}  |  {short}", fill="black", font=body_font)
        y += 36

        for line in textwrap.wrap(detailed, width=84):
            d.text((margin_x + 18, y), line, fill="#111111", font=small_font)
            y += 24
        y += 18

    y += 10
    d.line([(margin_x, y), (W - margin_x, y)], fill="#555555", width=2)
    y += 18
    d.text((margin_x, y), "Source: weather.gov", fill="#444444", font=small_font)

    d.rectangle((30, 30, W - 30, H - 30), outline="#777777", width=2)
    img.save(output_path, "PNG")
    print(f"Saved {output_path}")

def main():
    city, state, periods = get_forecast()
    draw_text_forecast(city, state, periods, OUTPUT)

if __name__ == "__main__":
    main()