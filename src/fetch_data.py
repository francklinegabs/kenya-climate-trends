"""Download daily weather history for five Kenyan cities from the Open-Meteo archive (ERA5 reanalysis).

Writes data/daily_weather.csv with one row per city per day.
Run:  python src/fetch_data.py
"""
from __future__ import annotations

import csv
import json
import time
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

CITIES = {
    "Nairobi": (-1.2864, 36.8172),
    "Mombasa": (-4.0435, 39.6682),
    "Kisumu": (-0.0917, 34.7680),
    "Eldoret": (0.5143, 35.2698),
    "Garissa": (-0.4532, 39.6461),
}

START, END = "1981-01-01", "2025-12-31"
VARS = ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean", "precipitation_sum"]
URL = (
    "https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
    "&start_date={start}&end_date={end}&daily={vars}&timezone=Africa%2FNairobi"
)


def fetch_city(lat: float, lon: float) -> dict:
    url = URL.format(lat=lat, lon=lon, start=START, end=END, vars=",".join(VARS))
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return json.load(resp)
        except Exception:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def main() -> None:
    DATA.mkdir(exist_ok=True)
    out = DATA / "daily_weather.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["city", "date", "tmax", "tmin", "tmean", "precip_mm"])
        for city, (lat, lon) in CITIES.items():
            daily = fetch_city(lat, lon)["daily"]
            n = len(daily["time"])
            for i in range(n):
                writer.writerow(
                    [city, daily["time"][i]]
                    + [daily[v][i] for v in VARS]
                )
            print(f"{city:<8} {n} days")
            time.sleep(1)  # be polite to the free API
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
