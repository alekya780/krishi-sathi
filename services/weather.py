from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import isfinite

import requests

DISTRICTS = {
    "Tirupati": (13.6288, 79.4192),
    "Anantapur": (14.6819, 77.6006),
    "Kurnool": (15.8281, 78.0373),
    "Guntur": (16.3067, 80.4365),
    "Visakhapatnam": (17.6868, 83.2185),
}
IST = timezone(timedelta(hours=5, minutes=30))
URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class Day:
    date: date
    low: float
    high: float
    rain: float


@dataclass(frozen=True)
class Forecast:
    temperature: float
    code: int
    days: tuple[Day, ...]
    retrieved: datetime


def fetch_forecast(district: str) -> Forecast | None:
    lat, lon = DISTRICTS[district]
    try:
        response = requests.get(
            URL,
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,weather_code",
                "daily": "temperature_2m_min,temperature_2m_max,rain_sum,showers_sum",
                "forecast_days": 3, "timezone": "Asia/Kolkata",
            },
            timeout=(4, 8),
        )
        response.raise_for_status()
        data = response.json()
        daily = data["daily"]
        days = tuple(
            Day(date.fromisoformat(day), float(low), float(high), float(rain) + float(showers))
            for day, low, high, rain, showers in zip(
                daily["time"], daily["temperature_2m_min"], daily["temperature_2m_max"],
                daily["rain_sum"], daily["showers_sum"], strict=True,
            )
        )
        temperature = float(data["current"]["temperature_2m"])
        code = int(data["current"]["weather_code"])
        if len(days) != 3 or not isfinite(temperature) or any(
            not all(map(isfinite, (day.low, day.high, day.rain)))
            or day.low > day.high or day.rain < 0
            for day in days
        ):
            return None
        return Forecast(temperature, code, days, datetime.now(IST))
    except (requests.RequestException, KeyError, TypeError, ValueError, OverflowError):
        return None


def condition(code: int) -> str:
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "thunder"
    return "unknown"
