import json
from dataclasses import dataclass
from pathlib import Path

from services.alerts import HEAT_C, HEAVY_RAIN_MM
from services.weather import Forecast

CROPS = json.loads((Path(__file__).resolve().parents[1] / "data/crops.json").read_text(encoding="utf-8"))
SOILS = ("Red", "Black", "Sandy", "Clay", "Loamy")
IRRIGATION = ("Rainfed", "Limited", "Adequate")
WATER = ("low", "medium", "high")


@dataclass(frozen=True)
class Recommendation:
    crop: str
    season_fit: bool
    water_fit: bool
    weather_note: str
    score: int


def season_for(month: int) -> str:
    if 6 <= month <= 10:
        return "kharif"
    if month >= 11 or month <= 2:
        return "rabi"
    return "summer"


def describe(crop: str, irrigation: str, season: str, forecast: Forecast | None) -> Recommendation:
    row = CROPS[crop]
    water_fit = WATER.index(row["water"]) <= IRRIGATION.index(irrigation)
    season_fit = season in row["seasons"]
    weather_note, adjustment = "weather_neutral", 0
    if forecast is None:
        weather_note = "weather_missing"
    elif row["drainage"] and any(day.rain >= HEAVY_RAIN_MM for day in forecast.days):
        weather_note, adjustment = "crop_drainage", -1
    elif row["water"] != "low" and any(day.high >= HEAT_C for day in forecast.days):
        weather_note, adjustment = "crop_heat", -1
    score = (3 if water_fit else -4) + (2 if season_fit else 0) + adjustment
    return Recommendation(crop, season_fit, water_fit, weather_note, score)


def recommend(soil: str, irrigation: str, season: str, forecast: Forecast | None) -> list[Recommendation]:
    options = [
        describe(crop, irrigation, season, forecast)
        for crop, row in CROPS.items() if soil in row["soils"]
    ]
    return sorted(options, key=lambda item: (-item.score, item.crop))[:3]
