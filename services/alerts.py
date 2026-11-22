from dataclasses import dataclass

from services.weather import Day, Forecast

RAIN_MM = 10
HEAVY_RAIN_MM = 30
HEAT_C = 36


@dataclass(frozen=True)
class Alert:
    kind: str
    days: tuple[Day, ...]


def make_alerts(forecast: Forecast | None) -> tuple[Alert, ...]:
    if forecast is None:
        return ()
    days = forecast.days
    heavy = tuple(day for day in days if day.rain >= HEAVY_RAIN_MM)
    rain = tuple(day for day in days if RAIN_MM <= day.rain < HEAVY_RAIN_MM)
    heat = tuple(day for day in days if day.high >= HEAT_C)
    alerts = tuple(
        Alert(kind, matches)
        for kind, matches in (("heavy", heavy), ("wet", rain), ("heat", heat))
        if matches
    )
    return alerts or (Alert("normal", days),)
