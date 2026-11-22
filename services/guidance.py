from collections.abc import Callable

from services.alerts import Alert
from services.recommendations import CROPS, Recommendation
from services.weather import Day


def evidence(day: Day, t: Callable) -> str:
    return (
        f"{day.date:%d-%m-%Y} · {t('forecast_rain', rain=day.rain)} · "
        + t("forecast_range", low=day.low, high=day.high)
    )


def alert_action(kind: str, irrigation: str) -> str:
    return "rainfed_check" if kind == "wet" and irrigation == "Rainfed" else kind + "_action"


def alert_text(alert: Alert, t: Callable, irrigation: str) -> str:
    return (
        f"**{t(alert.kind)}** — {t(alert_action(alert.kind, irrigation))}\n\n"
        f"**{t('reason')}** · {t(alert.kind + '_reason')}\n\n"
        f"**{t('evidence')}** · " + " / ".join(evidence(day, t) for day in alert.days)
        + f"\n\n{t('uncertainty')}"
    )


def crop_text(item: Recommendation, soil: str, language: str, t: Callable) -> str:
    row = CROPS[item.crop]
    soil_key = "soil_fit" if soil in row["soils"] else "soil_mismatch"
    return " ".join((
        t(soil_key, soil=t(soil)),
        t("water_need", water=t(row["water"])) + ".",
        t("water_fit" if item.water_fit else "water_gap"),
        t("season_yes" if item.season_fit else "season_no"),
        t(item.weather_note),
        row["limits"][int(language == "te")],
    ))
