import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from services.llm import LLMConfig
from test_alerts import forecast

APP = Path(__file__).resolve().parents[1] / "app.py"


@patch("services.llm.read_config", new=lambda secrets: LLMConfig())
class DashboardTests(unittest.TestCase):
    @patch("services.weather.fetch_forecast", return_value=forecast((10, 36), (31, 29), (0, 28)))
    def test_farmer_journey(self, fetch):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Current temperature" in item.value for item in app.markdown))
        self.assertTrue(any("Heavy rain" in item.value for item in app.markdown))
        self.assertEqual(len(app.get("vega_lite_chart")), 1)
        app.selectbox(key="crop").set_value("Maize")
        app.selectbox(key="irrigation").set_value("Rainfed").run()
        self.assertTrue(any("Selected crop is Maize" in item.value for item in app.markdown))
        self.assertTrue(any("Your profile is rainfed" in item.value for item in app.markdown))
        app.selectbox(key="crop").set_value("Groundnut")
        app.selectbox(key="irrigation").set_value("Limited").run()
        app.segmented_control(key="navigation").set_value("choices").run()
        self.assertTrue(any("Groundnut" in item.value for item in app.markdown))
        app.selectbox(key="soil").set_value("Clay")
        app.selectbox(key="irrigation").set_value("Adequate").run()
        self.assertTrue(any("Paddy" in item.value for item in app.markdown))
        app.segmented_control(key="navigation").set_value("market").run()
        self.assertIn("not live mandi prices", app.warning[0].value)
        app.selectbox(key="market_crop").set_value("Groundnut").run()
        self.assertEqual(len(app.dataframe[0].value), 2)
        self.assertEqual(len(app.get("vega_lite_chart")), 1)
        app.selectbox(key="language").set_value("te")
        app.segmented_control(key="navigation").set_value("ask").run()
        app.button(key="suggest_rain").click().run()
        self.assertEqual(len(app.chat_message), 2)
        self.assertIn("నియమాల", app.chat_message[1].caption[0].value)
        self.assertIn("తిరుపతి", app.chat_message[1].markdown[0].value)
        app.chat_input(key="question").set_value("What pesticide dose should I use?").run()
        self.assertEqual(len(app.chat_message), 4)
        app.selectbox(key="language").set_value("en").run()
        self.assertIn("enough verified information", app.chat_message[3].markdown[0].value)
        app.button(key="clear_chat").click().run()
        self.assertFalse(app.chat_message)
        self.assertFalse(app.exception)
        fetch.assert_called_with("Tirupati")

    @patch("services.weather.fetch_forecast", return_value=None)
    def test_weather_outage(self, fetch):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        app.selectbox(key="district").set_value("Guntur").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.warning[0].value, "Live weather unavailable")
        self.assertFalse(app.get("vega_lite_chart"))
        app.button[0].click().run()
        self.assertEqual(app.warning[0].value, "Live weather unavailable")
        app.segmented_control(key="navigation").set_value("choices").run()
        self.assertTrue(any("weather did not affect" in item.value for item in app.markdown))
        self.assertFalse(app.exception)
