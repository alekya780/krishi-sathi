import re
from datetime import date
from functools import partial

from services.alerts import HEAT_C, HEAVY_RAIN_MM, RAIN_MM, make_alerts
from services.guidance import alert_text, crop_text, evidence
from services.i18n import translate
from services.recommendations import CROPS, SOILS, describe, recommend
from services.weather import Forecast


def answer(
    question: str, language: str, district: str, soil: str, crop: str,
    irrigation: str, season: str, forecast: Forecast | None, today: date,
) -> str:
    t = partial(translate, language=language)
    q = question.casefold()

    def mentions(*terms: str) -> bool:
        return any(
            bool(re.search(r"\b" + re.escape(term.casefold()) + r"\b", q))
            if term.isascii() else term in q
            for term in terms
        )

    if not q.strip() or mentions(
        "pesticide", "dosage", "dose", "yield", "profit", "price", "fertilizer",
        "spray", "పురుగుమందు", "మోతాదు", "దిగుబడి", "ధర", "లాభం", "ఎరువు", "పిచికారీ",
    ):
        return t("unsupported")
    if mentions("alert", "alerts", "warning", "హెచ్చరిక", "సూచన అంటే"):
        return "\n\n".join(
            alert_text(item, t, irrigation) for item in make_alerts(forecast)
        ) or t("unavailable")
    if mentions("irrigate", "irrigation", "నీటితడి", "నీరు పెట్ట", "నీళ్లు పెట్ట"):
        guidance = t("rainfed_check" if irrigation == "Rainfed" else "today_checks")
        day = next((day for day in forecast.days if day.date == today), None) if forecast else None
        if day is None:
            return f"{t('unavailable')}. {guidance}"
        details = [t("forecast_today", district=t(district), rain=day.rain, heat=day.high), guidance]
        if day.rain >= HEAVY_RAIN_MM:
            details.append(t("heavy_action"))
        elif day.rain >= RAIN_MM and irrigation != "Rainfed":
            details.append(t("wet_action"))
        if day.high >= HEAT_C:
            details.append(t("heat_action"))
        return " ".join(details)
    if mentions("rain", "rainfall", "showers", "వర్షం", "వర్షపాతం"):
        if forecast is None:
            return t("unavailable")
        return t("rain_answer", district=t(district), days=" / ".join(
            evidence(day, t) for day in forecast.days
        ))
    requested_soil = next(
        (name for name in SOILS if mentions(name, translate(name, "te"))), None
    )
    if requested_soil or mentions("soil", "నేల", "మట్టి"):
        target_soil = requested_soil or soil
        records = recommend(target_soil, irrigation, season, forecast)
        return "\n\n".join(
            f"**{t(item.crop)}** · {crop_text(item, target_soil, language, t)}"
            for item in records
        ) + "\n\n" + t("verify")
    if mentions("plant", "planting", "sow", "sowing", "విత్త", "నాట", "సాగు"):
        target = next(
            (name for name in CROPS if mentions(name, translate(name, "te"))), None
        )
        if target or mentions("crop", "my crop", "పంట"):
            item = describe(target or crop, irrigation, season, forecast)
            return f"**{t(item.crop)}** · {crop_text(item, soil, language, t)}\n\n{t('verify')}"
    return t("unsupported")
