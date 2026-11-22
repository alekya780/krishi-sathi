import unittest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch

import requests

from services.alerts import make_alerts
from services.weather import IST, Day, Forecast, fetch_forecast

TODAY = date(2026, 11, 22)


def forecast(*values):
    days = tuple(Day(TODAY + timedelta(days=index), 22, high, rain)
                 for index, (rain, high) in enumerate(values))
    return Forecast(29, 0, days, datetime(2026, 11, 22, 9, tzinfo=IST))


class AlertTests(unittest.TestCase):
    def test_thresholds_and_matching_dates(self):
        weather = forecast((9.9, 35.9), (10, 36), (30, 32))
        heavy, wet, heat = make_alerts(weather)
        self.assertEqual([heavy.kind, wet.kind, heat.kind], ["heavy", "wet", "heat"])
        self.assertEqual(heavy.days, (weather.days[2],))
        self.assertEqual(wet.days, (weather.days[1],))
        self.assertEqual(heat.days, (weather.days[1],))

    def test_normal_and_missing(self):
        weather = forecast((9.9, 35.9))
        self.assertEqual(make_alerts(weather)[0].kind, "normal")
        self.assertFalse(make_alerts(None))

    @patch("services.weather.requests.get")
    def test_timeout_and_malformed_payload(self, get):
        get.side_effect = requests.Timeout
        self.assertIsNone(fetch_forecast("Tirupati"))
        get.side_effect = None
        get.return_value = Mock()
        get.return_value.json.return_value = {"daily": {}}
        self.assertIsNone(fetch_forecast("Tirupati"))

    @patch("services.weather.requests.get")
    def test_open_meteo_response(self, get):
        get.return_value.json.return_value = {
            "daily": {
                "time": ["2026-11-22", "2026-11-23", "2026-11-24"],
                "temperature_2m_min": [21, 22, 20],
                "temperature_2m_max": [36, 30, 31],
                "rain_sum": [1, 10, 29],
                "showers_sum": [0, 0, 1],
            },
            "current": {"temperature_2m": 29.6, "weather_code": 80},
        }
        weather = fetch_forecast("Tirupati")
        self.assertEqual(weather.temperature, 29.6)
        self.assertEqual(weather.days[2].rain, 30)
        params = get.call_args.kwargs["params"]
        self.assertEqual(params["timezone"], "Asia/Kolkata")
        self.assertEqual(params["forecast_days"], 3)
