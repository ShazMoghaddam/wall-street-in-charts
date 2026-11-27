"""Fit the forecast models, run the scenarios and the backtest.

Usage (from the repo root):

    python models/run.py

Writes to models/:
- forecast_annual.csv: history and bad / p25 / middling / p75 / good to 2035 ($ billions)
- backtest_annual.csv: 2021-2025 predictions from models trained on 2015-2020
- model_terms.csv: every equation's coefficients, fit (R²) and error persistence
- drivers_annual.csv: simulated market level (2025 = 100) and Fed funds rate
- settings.json: seed, simulation count and other run settings

The seed is fixed, so results repeat exactly. See wallstreet/forecast.py for
how the models work. Not financial advice.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wallstreet import forecast  # noqa: E402

OUT = ROOT / "models"
MONEY = ["actual", "bad", "p25", "middling", "p75", "good", "predicted_with_real_drivers"]


def to_billions(df):
    df = df.copy()
    for col in MONEY:
        if col in df:
            df[col] = (df[col] / 1e9).round(2)
    return df


def main() -> None:
    result = forecast.run_forecast()
    to_billions(result["forecast"]).to_csv(OUT / "forecast_annual.csv", index=False)
    result["models"].round(4).to_csv(OUT / "model_terms.csv", index=False)
    result["drivers"].round(2).to_csv(OUT / "drivers_annual.csv", index=False)
    settings = {k: (v.item() if hasattr(v, "item") else v) for k, v in result["settings"].items()}
    (OUT / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")

    backtest = to_billions(forecast.run_backtest())
    backtest["error_pct"] = backtest["error_pct"].round(4)
    backtest.to_csv(OUT / "backtest_annual.csv", index=False)
    print("wrote models/forecast_annual.csv, backtest_annual.csv, model_terms.csv,")
    print("      drivers_annual.csv and settings.json")


if __name__ == "__main__":
    main()
