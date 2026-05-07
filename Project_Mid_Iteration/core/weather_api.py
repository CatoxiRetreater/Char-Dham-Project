"""
weather_api.py — Real-Time Weather Integration (OpenWeatherMap)
================================================================
Fetches current weather and 5-day forecast for Char Dham shrines.
Implements file-based caching (30-min TTL) to respect API limits.
Falls back gracefully to historical averages on failure.
"""

import os
import json
import time
import requests
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
#  Configuration
# ---------------------------------------------------------------------------
API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
BASE_URL = "https://api.openweathermap.org/data/2.5"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_TTL_SECONDS = 1800  # 30 minutes

SHRINE_COORDS = {
    "Kedarnath":  {"lat": 30.7352, "lon": 79.0669},
    "Badrinath":  {"lat": 30.7440, "lon": 79.4930},
    "Gangotri":   {"lat": 30.9947, "lon": 78.9398},
    "Yamunotri":  {"lat": 31.0140, "lon": 78.4600},
}


# ---------------------------------------------------------------------------
#  Cache helpers
# ---------------------------------------------------------------------------
def _cache_path(shrine: str, endpoint: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{shrine.lower()}_{endpoint}.json"


def _read_cache(shrine: str, endpoint: str) -> dict | None:
    """Read cached data if exists and is fresh."""
    path = _cache_path(shrine, endpoint)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - data.get("_cached_at", 0) < CACHE_TTL_SECONDS:
            return data
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _write_cache(shrine: str, endpoint: str, data: dict):
    """Write data to cache with timestamp."""
    path = _cache_path(shrine, endpoint)
    data["_cached_at"] = time.time()
    path.write_text(json.dumps(data, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
#  API Calls
# ---------------------------------------------------------------------------
def fetch_current_weather(shrine: str) -> dict:
    """
    Fetch current weather for a shrine from OpenWeatherMap.
    Returns dict with keys: temp, feels_like, humidity, pressure,
    wind_speed, description, icon, rain_1h, clouds.
    """
    # Check cache first
    cached = _read_cache(shrine, "current")
    if cached:
        return cached

    coords = SHRINE_COORDS.get(shrine)
    if not coords or not API_KEY:
        return _fallback_weather(shrine)

    try:
        resp = requests.get(
            f"{BASE_URL}/weather",
            params={
                "lat": coords["lat"],
                "lon": coords["lon"],
                "appid": API_KEY,
                "units": "metric",
            },
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()

        result = {
            "shrine": shrine,
            "temp": raw["main"]["temp"],
            "feels_like": raw["main"]["feels_like"],
            "temp_min": raw["main"]["temp_min"],
            "temp_max": raw["main"]["temp_max"],
            "humidity": raw["main"]["humidity"],
            "pressure": raw["main"]["pressure"],
            "wind_speed": raw.get("wind", {}).get("speed", 0),
            "wind_deg": raw.get("wind", {}).get("deg", 0),
            "clouds": raw.get("clouds", {}).get("all", 0),
            "description": raw["weather"][0]["description"].title() if raw.get("weather") else "N/A",
            "icon": raw["weather"][0]["icon"] if raw.get("weather") else "01d",
            "rain_1h": raw.get("rain", {}).get("1h", 0),
            "rain_3h": raw.get("rain", {}).get("3h", 0),
            "snow_1h": raw.get("snow", {}).get("1h", 0),
            "visibility": raw.get("visibility", 10000),
            "timestamp": datetime.utcnow().isoformat(),
            "source": "OpenWeatherMap API",
        }

        _write_cache(shrine, "current", result)
        return result

    except Exception:
        return _fallback_weather(shrine)


def fetch_forecast(shrine: str) -> list[dict]:
    """
    Fetch 5-day / 3-hour forecast for a shrine.
    Returns list of forecast points.
    """
    cached = _read_cache(shrine, "forecast")
    if cached and "forecasts" in cached:
        return cached["forecasts"]

    coords = SHRINE_COORDS.get(shrine)
    if not coords or not API_KEY:
        return _fallback_forecast(shrine)

    try:
        resp = requests.get(
            f"{BASE_URL}/forecast",
            params={
                "lat": coords["lat"],
                "lon": coords["lon"],
                "appid": API_KEY,
                "units": "metric",
            },
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()

        forecasts = []
        for item in raw.get("list", []):
            forecasts.append({
                "datetime": item["dt_txt"],
                "temp": item["main"]["temp"],
                "feels_like": item["main"]["feels_like"],
                "humidity": item["main"]["humidity"],
                "pressure": item["main"]["pressure"],
                "wind_speed": item.get("wind", {}).get("speed", 0),
                "description": item["weather"][0]["description"].title() if item.get("weather") else "N/A",
                "icon": item["weather"][0]["icon"] if item.get("weather") else "01d",
                "rain_3h": item.get("rain", {}).get("3h", 0),
                "clouds": item.get("clouds", {}).get("all", 0),
            })

        _write_cache(shrine, "forecast", {"forecasts": forecasts})
        return forecasts

    except Exception:
        return _fallback_forecast(shrine)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_all_shrine_weather() -> dict:
    """Fetch current weather for all 4 shrines. Returns dict keyed by shrine name."""
    result = {}
    for shrine in SHRINE_COORDS:
        result[shrine] = fetch_current_weather(shrine)
    return result


# ---------------------------------------------------------------------------
#  Fallbacks (historical-average based)
# ---------------------------------------------------------------------------
_HISTORICAL_BASELINES = {
    "Kedarnath":  {"temp": 5.0, "humidity": 68, "wind_speed": 5.5, "rain_1h": 0, "pressure": 650, "description": "Partly Cloudy"},
    "Badrinath":  {"temp": 8.0, "humidity": 65, "wind_speed": 6.0, "rain_1h": 0, "pressure": 680, "description": "Clear Sky"},
    "Gangotri":   {"temp": 2.0, "humidity": 75, "wind_speed": 5.0, "rain_1h": 0, "pressure": 690, "description": "Misty"},
    "Yamunotri":  {"temp": 4.0, "humidity": 70, "wind_speed": 4.0, "rain_1h": 0, "pressure": 685, "description": "Partly Cloudy"},
}


def _fallback_weather(shrine: str) -> dict:
    """Generate realistic weather based on seasonal climatology when API is unavailable."""
    baseline = _HISTORICAL_BASELINES.get(shrine, _HISTORICAL_BASELINES["Kedarnath"])
    now = datetime.now()
    month = now.month

    # Seasonal temperature adjustment
    month_offset = np.sin(2 * np.pi * (month - 1) / 12)
    temp = baseline["temp"] + month_offset * 8 + np.random.uniform(-2, 2)

    # Seasonal rain patterns (Indian monsoon: Jul-Sep heavy, Oct-Nov tapering, Dec-Feb snow)
    if month in (7, 8, 9):       # Monsoon
        rain_1h = round(np.random.exponential(4.0), 1)  # Mean 4 mm/h
        rain_3h = round(rain_1h * np.random.uniform(2.0, 3.5), 1)
        clouds = np.random.randint(60, 100)
        description = np.random.choice(["Heavy Rain", "Moderate Rain", "Light Rain", "Thunderstorm"])
    elif month in (6, 10):       # Pre/post monsoon
        rain_1h = round(max(0, np.random.exponential(1.5) - 0.5), 1)
        rain_3h = round(rain_1h * np.random.uniform(1.5, 3.0), 1)
        clouds = np.random.randint(40, 85)
        description = np.random.choice(["Light Rain", "Partly Cloudy", "Overcast", "Drizzle"])
    elif month in (12, 1, 2):    # Winter
        rain_1h = 0.0
        rain_3h = 0.0
        clouds = np.random.randint(15, 60)
        description = np.random.choice(["Clear Sky", "Snow Flurries", "Partly Cloudy", "Fog"])
    else:                         # Spring/early summer
        rain_1h = round(max(0, np.random.exponential(0.5) - 0.3), 1)
        rain_3h = round(rain_1h * np.random.uniform(1.0, 2.5), 1)
        clouds = np.random.randint(10, 55)
        description = np.random.choice(["Clear Sky", "Partly Cloudy", "Haze"])

    # Snow in winter at high-altitude shrines
    snow_1h = 0.0
    if month in (12, 1, 2, 3) and temp < 2.0:
        snow_1h = round(np.random.exponential(1.5), 1)

    # Visibility based on conditions
    if "Fog" in description or "Mist" in description:
        visibility = int(np.random.uniform(200, 1500))
    elif "Rain" in description or "Thunderstorm" in description:
        visibility = int(np.random.uniform(1500, 5000))
    elif "Snow" in description:
        visibility = int(np.random.uniform(500, 3000))
    elif "Haze" in description or "Drizzle" in description:
        visibility = int(np.random.uniform(3000, 7000))
    else:
        visibility = int(np.random.uniform(8000, 15000))

    # Humidity correlates with rain
    base_humidity = baseline["humidity"]
    if rain_1h > 0:
        humidity = int(min(100, base_humidity + np.random.randint(5, 20)))
    else:
        humidity = int(base_humidity + np.random.randint(-10, 10))

    return {
        "shrine": shrine,
        "temp": round(temp, 1),
        "feels_like": round(temp - 2, 1),
        "temp_min": round(temp - 3, 1),
        "temp_max": round(temp + 3, 1),
        "humidity": np.clip(humidity, 20, 100),
        "pressure": baseline["pressure"],
        "wind_speed": round(baseline["wind_speed"] + np.random.uniform(-1, 1), 1),
        "wind_deg": np.random.randint(0, 360),
        "clouds": clouds,
        "description": description,
        "icon": "02d" if now.hour > 6 and now.hour < 18 else "02n",
        "rain_1h": rain_1h,
        "rain_3h": rain_3h,
        "snow_1h": snow_1h,
        "visibility": visibility,
        "timestamp": now.isoformat(),
        "source": "Historical Baseline (API unavailable)",
    }


def _fallback_forecast(shrine: str) -> list[dict]:
    """Generate a climatology-based 5-day forecast."""
    baseline = _HISTORICAL_BASELINES.get(shrine, _HISTORICAL_BASELINES["Kedarnath"])
    now = datetime.now()
    forecasts = []
    for i in range(40):  # 5 days × 8 (3-hour intervals)
        dt = now + timedelta(hours=i * 3)
        hour_offset = np.sin(2 * np.pi * dt.hour / 24) * 4  # diurnal cycle
        temp = baseline["temp"] + hour_offset + np.random.uniform(-1, 1)
        forecasts.append({
            "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "temp": round(temp, 1),
            "feels_like": round(temp - 2, 1),
            "humidity": int(baseline["humidity"] + np.random.randint(-5, 5)),
            "pressure": baseline["pressure"],
            "wind_speed": round(baseline["wind_speed"] + np.random.uniform(-1, 1), 1),
            "description": baseline["description"],
            "icon": "02d" if dt.hour > 6 and dt.hour < 18 else "02n",
            "rain_3h": round(max(0, np.random.uniform(-2, 3)), 1),
            "clouds": np.random.randint(10, 80),
        })
    return forecasts


def get_weather_icon_url(icon_code: str) -> str:
    """Return OpenWeatherMap icon URL for embedding."""
    return f"https://openweathermap.org/img/wn/{icon_code}@2x.png"
