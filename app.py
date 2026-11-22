from base64 import b64encode
from datetime import datetime
from functools import partial
from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from services.alerts import make_alerts
from services.assistant import answer
from services.guidance import alert_action, crop_text, evidence
from services.i18n import translate
from services.llm import build_context, generate, read_config
from services.recommendations import CROPS, IRRIGATION, SOILS, recommend, season_for
from services.weather import DISTRICTS, IST, condition, fetch_forecast

ROOT = Path(__file__).resolve().parent
WEATHER_ICONS = {
    "clear": "☀️", "cloudy": "⛅", "fog": "🌫️", "rain": "🌧️",
    "snow": "❄️", "thunder": "⛈️", "unknown": "—",
}
SEVERITY = {"normal": "informational", "wet": "informational", "heat": "caution", "heavy": "warning"}


@st.cache_data(ttl=600, show_spinner=False)
def cached_forecast(district):
    return fetch_forecast(district)


@st.cache_data
def market_prices():
    return pd.read_csv(ROOT / "data/mandi_sample.csv")


@st.cache_data
def hero_image():
    path = ROOT / "assets/fields.webp"
    return b64encode(path.read_bytes()).decode("ascii") if path.is_file() else ""


def markup(html):
    st.markdown(html, unsafe_allow_html=True)


def heading(title, detail=""):
    caption = f"<p>{escape(detail)}</p>" if detail else ""
    markup(f'<div class="ks-heading"><h2>{escape(title)}</h2>{caption}</div>')


def metric_card(icon, label, value):
    return (
        f'<div class="ks-weather-card"><span class="ks-icon" aria-hidden="true">{icon}</span>'
        f"<div><small>{escape(label)}</small><strong>{escape(value)}</strong></div></div>"
    )


def rain_chart(days, t):
    values = pd.DataFrame({"day": [day.date.isoformat() for day in days], "rain": [day.rain for day in days]})
    return alt.Chart(values).mark_bar(color="#168B65", size=32, cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
        x=alt.X("day:O", title=t("date"), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("rain:Q", title=t("rain_mm"), scale=alt.Scale(domainMin=0, domainMax=max(1, values["rain"].max()))),
        tooltip=[alt.Tooltip("day:O", title=t("date")), alt.Tooltip("rain:Q", title=t("rain_mm"), format=".1f")],
    ).properties(height=174)


def show_alert_explanation(alert, config, profile, language, season, forecast, today, t):
    cache = st.session_state.setdefault("alert_explanations", {})
    snapshot = (profile, language, season, today, forecast.days)
    previous = cache.get(alert.kind)
    if previous and previous[0] == snapshot:
        st.caption(t("ai_alert_title"))
        st.text(previous[1])
    elif st.button(t("ai_alert_button"), key=f"explain_{alert.kind}"):
        with st.spinner(t("ai_working")):
            context = build_context(*profile, season, forecast, today)
            explanation = generate(config, language, context, alert=alert)
        if explanation:
            cache[alert.kind] = (snapshot, explanation)
            st.rerun()
        else:
            st.warning(t("ai_alert_failed"))


def show_weather(forecast, profile, config, language, season, today, t):
    district, _, crop, irrigation = profile
    heading(t("weather_summary", district=t(district)))
    if forecast is None:
        st.warning(t("unavailable"))
        if st.button(t("retry")):
            cached_forecast.clear(district)
            st.rerun()
    else:
        weather = condition(forecast.code)
        total = sum(day.rain for day in forecast.days)
        metrics = [
            metric_card("🌡️", t("now"), f"{forecast.temperature:g} °C"),
            metric_card(WEATHER_ICONS[weather], t("conditions"), t(weather)),
            metric_card("💧", t("total"), f"{total:.1f} {t('mm')}"),
        ]
        markup('<div class="ks-grid" aria-label="' + escape(t("weather_summary", district=t(district))) + '">' +
               "".join(metrics) + "</div>")
        st.caption(t("retrieved", time=forecast.retrieved.strftime("%d-%m-%Y %H:%M")))

    heading(t("actions"), t("context", crop=t(crop), water=t(irrigation)))
    alerts = make_alerts(forecast)
    if alerts and config.api_key:
        st.caption(t("ai_rule_alerts"))
        st.caption(t("ai_alert_privacy"))
    for alert in alerts:
        kind = alert.kind
        action = alert_action(kind, irrigation)
        data = " / ".join(evidence(day, t) for day in alert.days)
        markup(
            f'<article class="ks-alert {kind}"><span class="ks-level">{escape(t(SEVERITY[kind]))}</span>'
            f'<h3>{escape(t(kind))}</h3><p class="ks-action">{escape(t(action))}</p>'
            f'<p><strong>{escape(t("reason"))}</strong> · {escape(t(kind + "_reason"))}</p>'
            f'<p><strong>{escape(t("evidence"))}</strong> · {escape(data)}</p>'
            f'<p class="ks-limits">{escape(t("uncertainty"))}</p></article>'
        )
        if config.api_key:
            show_alert_explanation(alert, config, profile, language, season, forecast, today, t)
    if forecast is None:
        st.info(t("no_actions"))
    st.caption(t("prototype"))

    if forecast is not None:
        heading(t("forecast"))
        cards = "".join(
            f'<article class="ks-weather-card ks-forecast"><strong>{day.date:%d-%m-%Y}</strong>'
            f'<p>{escape(t("forecast_range", low=day.low, high=day.high))}</p>'
            f'<p>{escape(t("forecast_rain", rain=day.rain))}</p></article>'
            for day in forecast.days
        )
        markup(f'<div class="ks-grid">{cards}</div>')
        with st.container(border=True):
            st.subheader(t("rain_chart"))
            st.altair_chart(rain_chart(forecast.days, t), width="stretch")


def show_crops(soil, irrigation, season, forecast, language, t):
    heading(t("choices"), t("season", season=t(season)))
    items = recommend(soil, irrigation, season, forecast)
    if not items:
        st.info(t("empty_crops"))
        return
    st.caption(t("verify"))
    with st.container(key="crop_cards"):
        for index, (column, item) in enumerate(zip(st.columns(len(items)), items, strict=True)):
            row = CROPS[item.crop]
            with column, st.container(border=True, key=f"recommendation_{index}"):
                markup(
                    f'<div class="ks-crop"><h3>{escape(t(item.crop))}</h3>'
                    f'<span class="ks-chip">{escape(t("soil_indicator", soil=t(soil)))}</span>'
                    f'<p>{escape(t("water_need", water=t(row["water"])))}</p>'
                    f'<p>{escape(row["limits"][int(language == "te")])}</p></div>'
                )
                with st.expander(t("reasoning")):
                    st.write(crop_text(item, soil, language, t))


def show_market(t):
    heading(t("market"))
    st.warning(t("market_note"))
    choice = st.selectbox(t("filter"), ("all", *CROPS), format_func=t, key="market_crop")
    prices = market_prices()
    if choice != "all":
        prices = prices.loc[prices["crop"] == choice]
    if prices.empty:
        st.info(t("empty_market"))
        return
    prices = prices.assign(
        crop=prices["crop"].map(t), market=prices["market"].map(t), unit=prices["unit"].map(t)
    ).rename(columns={"market": "market_name"})
    chart_data = prices.assign(label=prices["crop"] + " · " + prices["market_name"])
    chart = alt.Chart(chart_data).mark_bar(color="#168B65", cornerRadiusEnd=4).encode(
        x=alt.X("price:Q", title=t("price"), axis=alt.Axis(tickCount=6)),
        y=alt.Y("label:N", title=None, sort="-x", axis=alt.Axis(labelLimit=120, labelOverlap=False)),
        tooltip=[
            alt.Tooltip("crop:N", title=t("market_crop_name")),
            alt.Tooltip("market_name:N", title=t("market_name")),
            alt.Tooltip("price:Q", title=t("price"), format=",.0f"),
            alt.Tooltip("unit:N", title=t("unit")),
            alt.Tooltip("sample_date:N", title=t("sample_date")),
        ],
    ).properties(height=max(165, 48 + 31 * len(prices)))
    with st.container(border=True):
        st.subheader(t("market_chart"))
        st.altair_chart(chart, width="stretch")
    table = prices.rename(columns={"crop": "market_crop_name"}).rename(columns=t)
    st.dataframe(table, hide_index=True, width="stretch")


def show_assistant(profile, season, forecast, today, language, config, t):
    heading(t("ask"), t("ask_help"))
    st.caption(t("ai_ready" if config.api_key else "ai_off"))
    if config.api_key:
        st.caption(t("ai_privacy"))
    conversations = st.session_state.setdefault("conversations", {})
    history = conversations.setdefault(profile, [])
    with st.container(horizontal=True, key="suggested_questions"):
        suggestion = None
        for key in ("suggest_rain", "suggest_irrigation", "suggest_soil"):
            if st.button(t(key), key=key):
                suggestion = t(key)
        if history and st.button(t("clear_chat"), key="clear_chat"):
            history.clear()
            st.rerun()
    with st.container(border=True, key="chat_panel"):
        for question, replies in history:
            with st.chat_message("user"):
                st.text(question)
            with st.chat_message("assistant", avatar="🌱"):
                if "generated" in replies:
                    st.caption(t("ai_generated"))
                    st.text(replies["generated"])
                else:
                    if replies.get("provider_failed"):
                        st.caption(t("ai_failed"))
                    st.caption(t("ai_fallback"))
                    st.markdown(replies[language])
        typed = st.chat_input(t("question"), max_chars=350, key="question")
        question = (suggestion or typed or "").strip()
        if question:
            if config.api_key and config.api_key in question:
                question = t("ai_redacted")
                history.append((question, {code: translate("unsupported", code) for code in ("en", "te")}))
                st.rerun()
            with st.chat_message("user"):
                st.text(question)
            with st.chat_message("assistant", avatar="🌱"):
                with st.spinner(t("chat_loading")):
                    generated = None
                    if config.api_key:
                        context = build_context(*profile, season, forecast, today)
                        generated = generate(config, language, context, question)
                    if generated:
                        replies = {"generated": generated}
                    else:
                        replies = {
                            code: answer(question, code, *profile, season, forecast, today)
                            for code in ("en", "te")
                        }
                        replies["provider_failed"] = bool(config.api_key)
            history.append((question, replies))
            st.rerun()


st.set_page_config(page_title="Krishi Sathi", page_icon="🌱", layout="wide")
st.html(f"<style>{(ROOT / 'assets/dashboard.css').read_text(encoding='utf-8')}</style>")
with st.sidebar:
    language = st.selectbox(
        "Language / భాష", ("en", "te"), format_func={"en": "English", "te": "తెలుగు"}.get, key="language",
    )
    t = partial(translate, language=language)
    st.header(t("profile"))
    district = st.selectbox(t("district"), DISTRICTS, format_func=t, key="district")
    soil = st.selectbox(t("soil"), SOILS, format_func=t, key="soil")
    crop = st.selectbox(t("crop"), CROPS, format_func=t, key="crop")
    irrigation = st.selectbox(t("irrigation"), IRRIGATION, index=1, format_func=t, key="irrigation")
    st.caption(t("soil_source"))

markup(f'<div class="ks-brand"><span class="ks-mark" aria-hidden="true">🌱</span>{escape(t("title"))}</div>')
section = st.segmented_control(
    t("nav"), ("overview", "choices", "market", "ask"),
    format_func=t, default="overview", required=True, wrap=True,
    key="navigation", label_visibility="collapsed",
)
if section == "overview":
    photo = hero_image()
    image = f'<img src="data:image/webp;base64,{photo}" alt="">' if photo else ""
    markup(
        f'<header class="ks-hero">{image}<div><h1>{escape(t("hero_heading"))}</h1>'
        f'<p>{escape(t("hero_summary"))}</p></div></header>'
    )

forecast = None
if section != "market":
    with st.spinner(t("loading_weather")):
        forecast = cached_forecast(district)
today = datetime.now(IST).date()
season = season_for(today.month)
profile = (district, soil, crop, irrigation)

if section == "overview":
    show_weather(forecast, profile, read_config(st.secrets), language, season, today, t)
elif section == "choices":
    show_crops(soil, irrigation, season, forecast, language, t)
elif section == "market":
    show_market(t)
else:
    show_assistant(profile, season, forecast, today, language, read_config(st.secrets), t)

markup(
    f'<footer class="ks-footer"><p>{escape(t("footer_source"))} · '
    f'<a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo</a></p>'
    f'<p>{escape(t("footer_note"))}</p></footer>'
)
