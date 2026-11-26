"""The forecast machinery: fitting, simulation and repeatability."""

import numpy as np
import pandas as pd
import pytest

from wallstreet import forecast as FC
from wallstreet.config import PROCESSED

if not (PROCESSED / "drivers_quarterly.csv").exists():
    pytest.skip("processed data not built", allow_module_level=True)


def test_ols_recovers_a_known_line():
    x = pd.Series(np.arange(20.0))
    y = 3 + 2 * x
    coef, resid, r2 = FC.ols(y, pd.DataFrame({"x": x}))
    assert coef["const"] == pytest.approx(3)
    assert coef["x"] == pytest.approx(2)
    assert r2 == pytest.approx(1)


def test_rates_never_go_negative():
    drv = FC.load_drivers()
    model = FC.fit_drivers(drv)
    sims = FC.simulate_drivers(model, drv.iloc[-1], 40, 500, np.random.default_rng(1))
    assert (sims["rate"] >= 0).all()
    assert sims["log_market"].shape == (500, 40)


def test_rate_pulls_towards_a_sensible_level():
    model = FC.fit_drivers(FC.load_drivers())
    assert 0 < model.rate_speed < 0.5
    assert 0.5 < model.rate_mean < 6


def test_same_seed_same_answer():
    a = FC.run_forecast(n_sims=300)["forecast"]
    b = FC.run_forecast(n_sims=300)["forecast"]
    pd.testing.assert_frame_equal(a, b)


def test_committed_forecast_matches_a_fresh_run():
    committed = pd.read_csv(FC.PROCESSED.parent.parent / "models" / "forecast_annual.csv")
    fresh = FC.run_forecast()["forecast"]
    fresh_mid = (fresh.dropna(subset=["middling"])["middling"] / 1e9).round(2).to_numpy()
    assert np.allclose(committed.dropna(subset=["middling"])["middling"].to_numpy(), fresh_mid)


def test_quarter_helpers():
    assert FC.future_quarters("2025Q4", "2026Q2") == ["2026Q1", "2026Q2"]
    t = FC.trend(["2015Q1", "2016Q1"])
    assert t.tolist() == [0.0, 1.0]
