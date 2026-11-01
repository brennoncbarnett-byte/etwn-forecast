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

