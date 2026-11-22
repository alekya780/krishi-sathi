import contextlib
import io
import json
import logging
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import streamlit as st
from openai import OpenAI
from streamlit.testing.v1 import AppTest

from services.alerts import make_alerts
from services.llm import DEFAULT_MODEL, LLMConfig, build_context, generate, read_config
from test_alerts import TODAY, forecast

PROFILE = ("Tirupati", "Red", "Groundnut", "Limited")
WEATHER = forecast((2.4, 32.1), (31.3, 36.2), (0, 29.7))
APP = Path(__file__).resolve().parents[1] / "app.py"
TEST_KEY = "test-private-provider-key-for-unit-tests"
CONFIG = LLMConfig(TEST_KEY)


def mock_client(handler):
    return patch("services.llm.OpenAI", side_effect=lambda **kwargs: OpenAI(
        **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler))
    ))


def completion(text):
    return httpx.Response(200, json={
        "id": "test-completion", "object": "chat.completion", "created": 0,
        "model": DEFAULT_MODEL,
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": text}}],
    })


class LLMTests(unittest.TestCase):
    def test_mocked_english_and_telugu_send_exact_context(self):
        context = build_context(*PROFILE, "rabi", WEATHER, TODAY)
        sent = []
        english = "Check whether planned irrigation can wait until you inspect the field."
        telugu = "పొలంలో తేమను చూసి నీటితడిపై నిర్ణయం తీసుకోండి."

        def handler(request):
            sent.append(json.loads(request.content))
            return completion(english if len(sent) == 1 else telugu)

        with mock_client(handler):
            self.assertEqual(generate(CONFIG, "en", context, "What should I check?"), english)
            self.assertEqual(generate(CONFIG, "te", context, "పొలంలో ఏమి చూడాలి?"), telugu)

        for sent_request, language, question in zip(
            sent, ("English", "Telugu"), ("What should I check?", "పొలంలో ఏమి చూడాలి?"), strict=True,
        ):
            self.assertEqual(sent_request["model"], DEFAULT_MODEL)
            self.assertEqual(sent_request["max_completion_tokens"], 650)
            self.assertFalse(sent_request["store"])
            self.assertNotIn(TEST_KEY, str(sent_request))
            system, user = sent_request["messages"]
            self.assertIn("Required reply language: " + language, system["content"])
            self.assertIn("untrusted", system["content"])
            payload = json.loads(user["content"])
            self.assertEqual(payload["farmer_question"], question)
            data = payload["verified_application_context"]
            self.assertEqual(data["farm_profile"]["farmer_selected_soil"], "Red")
            self.assertEqual(data["farm_profile"]["current_or_preferred_crop"], "Groundnut")
            self.assertEqual(data["farm_profile"]["district"], "Tirupati")
            self.assertEqual(data["farm_profile"]["irrigation_availability"], "Limited")
            self.assertIsNone(data["farm_profile"]["field_soil_moisture"])
            self.assertEqual(data["forecast"]["current_temperature_c"], 29)
            self.assertEqual(data["forecast"]["days"][1]["rain_mm"], 31.3)
            self.assertEqual(data["forecast"]["days"][1]["high_c"], 36.2)
            self.assertEqual(data["prototype_alerts"][0]["supporting_days"][0]["rain_mm"], 31.3)
            self.assertIn("Groundnut", data["prototype_crop_reference"])

    def test_alert_request_and_invalid_generation(self):
        context = build_context(*PROFILE, "rabi", WEATHER, TODAY)
        alert = make_alerts(WEATHER)[0]

        def handler(request):
            payload = json.loads(json.loads(request.content)["messages"][1]["content"])
            self.assertEqual(payload["selected_alert"]["detected_condition"], "Heavy rain forecast")
            self.assertNotIn("farmer_question", payload)
            return completion("Heavy rainfall of 99 mm is expected.")

        with mock_client(handler):
            self.assertIsNone(generate(CONFIG, "en", context, alert=alert))
        with mock_client(lambda _: completion(TEST_KEY)):
            self.assertIsNone(generate(CONFIG, "en", context, "Question"))
        with mock_client(lambda _: completion("English when Telugu was requested.")):
            self.assertIsNone(generate(CONFIG, "te", context, "ప్రశ్న"))

    def test_missing_key_missing_weather_and_rate_limit(self):
        context = build_context(*PROFILE, "rabi", None, TODAY)
        self.assertIsNone(context["forecast"])
        self.assertEqual(context["prototype_alerts"], [])
        with patch.dict(os.environ, {}, clear=True), patch("services.llm.ENV_FILE") as env_file:
            env_file.is_file.return_value = False
            self.assertFalse(read_config({}).api_key)
            self.assertEqual(read_config({"OPENAI_MODEL": "compatible-mini"}).model, "compatible-mini")
        with patch("services.llm.OpenAI") as sdk:
            self.assertIsNone(generate(LLMConfig(), "en", context, "Question"))
            self.assertIsNone(generate(CONFIG, "en", context, TEST_KEY))
            sdk.assert_not_called()

        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            with contextlib.redirect_stderr(log_output), mock_client(lambda _: httpx.Response(
                429, json={"error": {"message": f"Rate limit for {TEST_KEY}"}}
            )):
                self.assertIsNone(generate(CONFIG, "en", context, "Question"))
        finally:
            root.removeHandler(handler)
        self.assertNotIn(TEST_KEY, log_output.getvalue())


@patch("services.weather.fetch_forecast", return_value=WEATHER)
class LLMDashboardTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()

    def test_chat_and_alert_are_generated_only_on_request(self, fetch):
        generated = "Check drainage and inspect soil moisture before deciding on the next field operation."
        with patch("services.llm.read_config", return_value=CONFIG), patch(
            "services.llm.generate", return_value=generated,
        ) as request:
            app = AppTest.from_file(str(APP), default_timeout=15).run()
            request.assert_not_called()
            app.button(key="explain_heavy").click().run()
            self.assertEqual(request.call_count, 1)
            self.assertIn("AI-generated explanation", [item.value for item in app.caption])
            self.assertTrue(any("31.3 mm" in item.value for item in app.markdown))
            app.run()
            self.assertEqual(request.call_count, 1)
            app.segmented_control(key="navigation").set_value("ask").run()
            app.chat_input(key="question").set_value("How should I prioritize field checks?").run()
            self.assertEqual(request.call_count, 2)
            self.assertEqual(request.call_args.args[1], "en")
            self.assertEqual(app.chat_message[1].caption[0].value, "Generated by AI")
            app.selectbox(key="language").set_value("te").run()
            self.assertEqual(request.call_count, 2)
            request.return_value = "పొలంలో తేమను పరిశీలించండి."
            app.chat_input(key="question").set_value("పొలంలో ఏమి చూడాలి?").run()
            self.assertEqual(request.call_args.args[1], "te")
            self.assertIn("పొలంలో", app.chat_message[3].text[0].value)
            self.assertFalse(app.exception)

    def test_provider_error_falls_back_and_hides_credentials(self, fetch):
        with patch("services.llm.read_config", return_value=CONFIG), patch(
            "services.llm.generate", return_value=None,
        ):
            app = AppTest.from_file(str(APP), default_timeout=15).run()
            app.button(key="explain_heavy").click().run()
            self.assertIn("AI explanation unavailable", app.warning[0].value)
            self.assertTrue(any("Heavy rain forecast" in item.value for item in app.markdown))
            app.segmented_control(key="navigation").set_value("ask").run()
            app.button(key="suggest_rain").click().run()
            labels = [item.value for item in app.chat_message[1].caption]
            self.assertIn("Rule-based fallback", labels)
            self.assertNotIn("Generated by AI", labels)
            self.assertIn("did not return a usable reply", labels[0])
            app.chat_input(key="question").set_value(TEST_KEY).run()
            self.assertNotIn(TEST_KEY, str(app))
            self.assertFalse(app.exception)
