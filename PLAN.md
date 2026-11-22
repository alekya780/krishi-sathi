# Implementation plan

1. Create an isolated Streamlit project with farmer inputs and English/Telugu UI strings.
2. Connect Open-Meteo using representative district coordinates. Normalize current conditions and three local calendar days, and handle outages explicitly.
3. Turn forecast values into dated, explainable alerts. Rank reference crops by soil, irrigation, season, and forecast considerations.
4. Add filterable sample mandi data and bilingual Q&A grounded in the current farmer profile.
5. Verify live integration, outage behavior, threshold boundaries, and the complete dashboard flow. Document setup and the 90-second demo.
