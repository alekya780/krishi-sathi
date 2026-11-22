import unittest
from datetime import timedelta

from services.assistant import answer
from services.recommendations import CROPS, recommend, season_for
from test_alerts import TODAY, forecast


class RecommendationTests(unittest.TestCase):
    def test_soil_and_irrigation_change_results(self):
        rainfed = recommend("Red", "Rainfed", "rabi", None)
        limited = recommend("Red", "Limited", "rabi", None)
        adequate = recommend("Clay", "Adequate", "rabi", None)
        self.assertEqual(rainfed[0].crop, "Millets")
        self.assertEqual(limited[0].crop, "Groundnut")
        self.assertEqual(adequate[0].crop, "Paddy")
        self.assertTrue(all("Red" in CROPS[item.crop]["soils"] for item in limited))
        self.assertLessEqual(len(limited), 3)

    def test_season_and_weather_explanations(self):
        self.assertEqual([season_for(month) for month in (1, 4, 7, 11)],
                         ["rabi", "summer", "kharif", "rabi"])
        records = recommend("Red", "Limited", "rabi", forecast((31, 28)))
        self.assertTrue(all(record.weather_note == "crop_drainage" for record in records))
        self.assertFalse(recommend("Red", "Limited", "summer", None)[0].season_fit)

    def test_supported_and_unsupported_questions(self):
        def ask(q, language="en", today=TODAY):
            return answer(q, language, "Tirupati", "Red", "Groundnut", "Limited",
                          "rabi", forecast((15, 34), (33, 37)), today)
        self.assertIn("15 mm", ask("Is rain expected in my district?"))
        self.assertIn("can wait", ask("Should I irrigate today?"))
        self.assertIn("Groundnut", ask("Which crops suit red soil?"))
        self.assertIn("well-drained", ask("What should I consider before planting groundnut?"))
        self.assertIn("Heavy rain forecast", ask("What does this weather alert mean?"))
        self.assertIn("తిరుపతి", ask("నా జిల్లాలో వర్షం పడుతుందా?", "te"))
        self.assertIn("వేరుశనగ", ask("వేరుశనగ విత్తే ముందు ఏం చూడాలి?", "te"))
        self.assertIn("enough verified information", ask("What pesticide dose suits red soil?"))
        self.assertIn("unavailable", ask("Should I irrigate today?", today=TODAY - timedelta(days=1)))
