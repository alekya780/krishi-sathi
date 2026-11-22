# Krishi Sathi in 90 seconds

Before the demo, configure the API key using [the setup guide](README.md#configure-generative-ai). Submit an English and a Telugu question and request an alert explanation. Check that each shows a generated label.

| Time | On screen | Narration |
| --- | --- | --- |
| 0–12 s | Open **Weather & actions**. Select **Tirupati**, **Red**, **Groundnut**, and **Limited**. | “This farmer is growing groundnut near Tirupati. They select the soil and irrigation available in their field.” |
| 12–25 s | Show current weather, three forecast days, and the Open-Meteo timestamp. | “The app retrieves current conditions and three local forecast days.” |
| 25–45 s | Read the actual action and select **Explain this alert with AI**. Point to the AI explanation and the dated evidence in the rule-based card. | “The alert rules determine the action. The model explains what to check for this farm, using the forecast and selected inputs.” For routine monitoring, explain that the forecast stayed below the demonstration thresholds. |
| 45–60 s | Open **Crop options** and expand a card's reasoning. | “The ranking takes red soil, limited irrigation, the current season and the latest forecast into account. Here is the trade-off for this crop.” |
| 60–73 s | Switch to **తెలుగు** and return to the weather action. | “The farmer can read the same forecast evidence and guidance in Telugu.” |
| 73–90 s | Open **కృషి సాథిని అడగండి** and ask **ఈ వాతావరణ అంచనా ప్రకారం వేరుశనగ రైతు ముందుగా ఏం చూడాలి?** Point to the generated label and read one sentence from the answer. | “The model responds in Telugu using the farmer’s selected crop and available weather data.” |

If Open-Meteo is unavailable, show the explicit outage state and retry once. Continue with crop options and the assistant's outage response. The mandi view is available for follow-up questions and labels every price as illustrative.

If the LLM request fails, point out the fallback label and continue with the deterministic guidance. Save the generative portion for a successful provider response.
