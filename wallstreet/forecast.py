"""Forecasts to 2030 and 2035: driver models plus Monte Carlo scenarios.

Two layers:

1. **Drivers** (the world): the total value of US public company shares,
   the Fed funds rate and the VIX. We simulate 10,000 futures by drawing
   whole blocks of real quarters from 1990 to 2025 (so crashes, rate cycles
   and calm spells come with their real timing and links between them):
   - market value: the block's actual quarterly change,
   - interest rate: pulled back towards its long-run level each quarter,
     plus the block's actual surprise,
   - VIX: its own persistence, plus how it reacts to the market, plus the
     block's actual surprise.
2. **Firms**: simple regressions link each firm to the drivers.
   - Banks: net interest income follows the interest rate and the size of
     the market (a stand-in for the economy and balance sheets); other revenue
     follows the market and the VIX (with quarter-of-year effects); profit
     margin follows the interest rate.
   - Fund managers: AUM follows the market plus a steady trend (new money);
     revenue follows AUM and rates; profit margin follows rates.
   Each model's leftover error is persistent (AR(1)) and is simulated too,
   so the range reflects how wrong the model has been, not just the drivers.

The 10th, 50th and 90th percentiles of the simulated outcomes are the bad,
middling and good scenarios. The random seed is fixed, so results repeat.

Not financial advice: these are illustrations of a simple model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import PROCESSED

SEED = 20251231
N_SIMS = 10_000
BLOCK = 4  # quarters per bootstrap block
HISTORY = ("2015Q1", "2025Q4")
BACKTEST_TRAIN = ("2015Q1", "2020Q4")
BACKTEST_TEST = ("2021Q1", "2025Q4")
DRIVER_WINDOW = ("1990Q1", "2025Q4")
HORIZON = "2035Q4"
PERCENTILES = {"bad": 10, "middling": 50, "good": 90}

BANKS = ["jpmorgan", "goldman", "morgan_stanley"]
FUND_MANAGERS = ["blackrock", "state_street"]


# Data -----------------------------------------------------------------------


def load_drivers() -> pd.DataFrame:
    """Quarterly drivers: log market value, Fed funds rate (%), log VIX."""
    df = pd.read_csv(PROCESSED / "drivers_quarterly.csv").set_index("quarter")
    return pd.DataFrame(
        {
            "log_market": np.log(df["market_value_usd"]),
            "rate": df["fed_funds"],
            "log_vix": np.log(df["vix"]),
        }
    )


def load_firm_data() -> pd.DataFrame:
    """Quarterly firm figures (wide): revenue, net income, NII and AUM by firm."""
    f = pd.read_csv(PROCESSED / "fundamentals_quarterly.csv")
    wide = f.pivot_table(index="quarter", columns=["firm", "metric"], values="value_usd")
    a = pd.read_csv(PROCESSED / "aum.csv")
    a = a[a["firm"].isin(FUND_MANAGERS)].copy()
    a["quarter"] = pd.PeriodIndex(pd.to_datetime(a["as_of"]), freq="Q").astype(str)
    for firm in FUND_MANAGERS:
        s = a[a["firm"] == firm].set_index("quarter")["aum_trillion_usd"] * 1e12
        wide[(firm, "aum")] = s
    return wide.sort_index(axis=1)


# Small tools ----------------------------------------------------------------


def ols(y: pd.Series, X: pd.DataFrame) -> tuple[pd.Series, pd.Series, float]:
    """Least squares with an intercept. Returns coefficients, residuals and R²."""
    X = X.assign(const=1.0)[["const", *X.columns]]
    beta, *_ = np.linalg.lstsq(X.to_numpy(float), y.to_numpy(float), rcond=None)
    coef = pd.Series(beta, index=X.columns)
    fitted = X.to_numpy(float) @ beta
    resid = y - fitted
    r2 = 1 - float((resid**2).sum()) / float(((y - y.mean()) ** 2).sum())
    return coef, resid, r2


def ar1(resid: pd.Series) -> tuple[float, np.ndarray]:
    """Persistence of the leftover error, and the surprises that remain."""
    r = resid.to_numpy(float)
    phi = float(np.clip(np.corrcoef(r[:-1], r[1:])[0, 1], 0.0, 0.95)) if len(r) > 3 else 0.0
    shocks = r[1:] - phi * r[:-1]
    return phi, shocks - shocks.mean()


def quarter_dummies(quarters) -> pd.DataFrame:
    q = pd.Series([int(x[-1]) for x in quarters], index=quarters)
    return pd.DataFrame({f"q{k}": (q == k).astype(float) for k in (2, 3, 4)}, index=quarters)


def trend(quarters, origin: str = HISTORY[0]) -> pd.Series:
    p = pd.PeriodIndex(quarters, freq="Q")
    return pd.Series((p - pd.Period(origin, freq="Q")).map(lambda d: d.n) / 4.0, index=quarters)


def future_quarters(after: str, until: str) -> list[str]:
    start = pd.Period(after, freq="Q") + 1
    return [str(p) for p in pd.period_range(start, pd.Period(until, freq="Q"), freq="Q")]


# Drivers ------------------------------------------------------------------


@dataclass
class DriverModel:
    rate_mean: float
    rate_speed: float
    vix_const: float
    vix_persist: float
    vix_market: float
    shocks: pd.DataFrame  # columns: market, rate, vix (one row per historical quarter)


def fit_drivers(drv: pd.DataFrame, window: tuple[str, str] = DRIVER_WINDOW) -> DriverModel:
    d = drv.loc[window[0] : window[1]]
    market = d["log_market"].diff()
    # Rate: change = speed * (mean - last rate) + surprise
    dr = d["rate"].diff()
    coef, rate_resid, _ = ols(dr.iloc[1:], pd.DataFrame({"last": d["rate"].shift(1).iloc[1:]}))
    speed = float(-coef["last"])
    mean = float(coef["const"] / speed) if speed > 0 else float(d["rate"].mean())
    # VIX: log VIX = c + persist * last + market_move * this quarter's market change
    X = pd.DataFrame({"last": d["log_vix"].shift(1), "market": market}).iloc[1:]
    vcoef, vix_resid, _ = ols(d["log_vix"].iloc[1:], X)
    shocks = pd.DataFrame(
        {"market": market.iloc[1:], "rate": rate_resid, "vix": vix_resid}
    ).dropna()
    return DriverModel(
        rate_mean=mean,
        rate_speed=speed,
        vix_const=float(vcoef["const"]),
        vix_persist=float(vcoef["last"]),
        vix_market=float(vcoef["market"]),
        shocks=shocks,
    )


def simulate_drivers(
    model: DriverModel, start: pd.Series, n_quarters: int, n_sims: int, rng: np.random.Generator
) -> dict[str, np.ndarray]:
    """Arrays of shape (n_sims, n_quarters): log_market, rate, log_vix."""
    shocks = model.shocks.to_numpy(float)
    n_hist = len(shocks)
    n_blocks = -(-n_quarters // BLOCK)
    starts = rng.integers(0, n_hist - BLOCK + 1, size=(n_sims, n_blocks))
    idx = (starts[:, :, None] + np.arange(BLOCK)).reshape(n_sims, -1)[:, :n_quarters]
    draw = shocks[idx]  # (sims, quarters, 3)
    log_market = start["log_market"] + np.cumsum(draw[:, :, 0], axis=1)
    rate = np.empty((n_sims, n_quarters))
    vix = np.empty((n_sims, n_quarters))
    r, v = np.full(n_sims, start["rate"]), np.full(n_sims, start["log_vix"])
    for t in range(n_quarters):
        r = np.maximum(r + model.rate_speed * (model.rate_mean - r) + draw[:, t, 1], 0.0)
        v = (
            model.vix_const
            + model.vix_persist * v
            + model.vix_market * draw[:, t, 0]
            + draw[:, t, 2]
        )
        rate[:, t], vix[:, t] = r, v
    return {"log_market": log_market, "rate": rate, "log_vix": vix}


# Firm models ----------------------------------------------------------------


@dataclass
class Equation:
    name: str
    target: str  # how y is built: "log_nii", "log_other", "margin", "log_aum", "log_revenue"
    terms: list[str]
    coef: pd.Series = field(default_factory=pd.Series)
    r2: float = 0.0
    phi: float = 0.0
    shocks: np.ndarray = field(default_factory=lambda: np.zeros(1))
    last_resid: float = 0.0
    n: int = 0


SPECS = {
    "bank": [
        Equation("net interest income", "log_nii", ["rate", "log_market"]),
        Equation("other revenue", "log_other", ["log_market", "log_vix", "q2", "q3", "q4"]),
        Equation("profit margin", "margin", ["rate", "log_vix"]),
    ],
    "fund_manager": [
        Equation("AUM", "log_aum", ["log_market", "trend"]),
        Equation("revenue", "log_revenue", ["log_aum", "rate"]),
        Equation("profit margin", "margin", ["rate", "log_vix"]),
    ],
}


def targets(firm_data: pd.DataFrame, firm: str) -> pd.DataFrame:
    d = firm_data[firm]
    out = pd.DataFrame(index=firm_data.index)
    out["log_revenue"] = np.log(d["revenue"])
    out["margin"] = d["net_income"] / d["revenue"]
    if "net_interest_income" in d:
        out["log_nii"] = np.log(d["net_interest_income"].clip(lower=1))
        out["log_other"] = np.log(d["revenue"] - d["net_interest_income"])
    if "aum" in d:
        out["log_aum"] = np.log(d["aum"])
    return out


def regressors(drv: pd.DataFrame, quarters, extra: dict | None = None) -> pd.DataFrame:
    X = drv.reindex(quarters)[["log_market", "rate", "log_vix"]].copy()
    X["trend"] = trend(quarters)
    X = X.join(quarter_dummies(quarters))
    for k, v in (extra or {}).items():
        X[k] = v
    return X


def group_of(firm: str) -> str:
    return "bank" if firm in BANKS else "fund_manager"


def fit_firm(firm: str, firm_data: pd.DataFrame, drv: pd.DataFrame, window) -> list[Equation]:
    quarters = [q for q in firm_data.index if window[0] <= q <= window[1]]
    y_all = targets(firm_data, firm).loc[quarters]
    X_all = regressors(drv, quarters, {"log_aum": y_all.get("log_aum")})
    fitted = []
    for spec in SPECS[group_of(firm)]:
        eq = Equation(spec.name, spec.target, list(spec.terms))
        y = y_all[eq.target].dropna()
        X = X_all.loc[y.index, eq.terms]
        eq.coef, resid, eq.r2 = ols(y, X)
        eq.phi, eq.shocks = ar1(resid)
        eq.last_resid = float(resid.iloc[-1])
        eq.n = len(y)
        fitted.append(eq)
    return fitted


def _predict(eq: Equation, X: dict[str, np.ndarray]) -> np.ndarray:
    out = eq.coef["const"]
    for term in eq.terms:
        out = out + eq.coef[term] * X[term]
    return out


def _residual_paths(eq: Equation, shape: tuple[int, int], rng, simulate: bool) -> np.ndarray:
    n_sims, n_q = shape
    e = np.empty(shape)
    last = np.full(n_sims, eq.last_resid)
    draws = rng.choice(eq.shocks, size=shape) if simulate else np.zeros(shape)
    for t in range(n_q):
        last = eq.phi * last + draws[:, t]
        e[:, t] = last
    return e


def simulate_firm(
    firm: str,
    eqs: list[Equation],
    drivers: dict[str, np.ndarray],
    quarters: list[str],
    rng: np.random.Generator,
    simulate_errors: bool = True,
) -> dict[str, np.ndarray]:
    """Quarterly revenue, profit (and AUM) paths in dollars, shape (sims, quarters)."""
    shape = drivers["log_market"].shape
    X = {k: drivers[k] for k in ("log_market", "rate", "log_vix")}
    X["trend"] = np.broadcast_to(trend(quarters).to_numpy(), shape)
    for k, col in quarter_dummies(quarters).items():
        X[k] = np.broadcast_to(col.to_numpy(), shape)
    eq = {e.target: e for e in eqs}
    out: dict[str, np.ndarray] = {}

    def solve(target: str) -> np.ndarray:
        e = eq[target]
        return _predict(e, X) + _residual_paths(e, shape, rng, simulate_errors)

    if group_of(firm) == "bank":
        nii = np.exp(solve("log_nii"))
        other = np.exp(solve("log_other"))
        revenue = nii + other
    else:
        X["log_aum"] = solve("log_aum")
        out["aum"] = np.exp(X["log_aum"])
        revenue = np.exp(solve("log_revenue"))
    margin = solve("margin")
    out["revenue"] = revenue
    out["net_income"] = margin * revenue
    return out


# Summaries ----------------------------------------------------------------


def annual(paths: dict[str, np.ndarray], quarters: list[str]) -> dict[str, pd.DataFrame]:
    """Yearly totals (revenue, profit) or year-end values (AUM), per simulation."""
    years = np.array([int(q[:4]) for q in quarters])
    out = {}
    for metric, arr in paths.items():
        cols = {}
        for y in np.unique(years):
            mask = years == y
            if metric == "aum":
                cols[y] = arr[:, np.where(mask)[0][-1]]
            else:
                cols[y] = arr[:, mask].sum(axis=1)
        out[metric] = pd.DataFrame(cols)
    return out


def percentiles(sims: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {name: np.percentile(sims.to_numpy(), p, axis=0) for name, p in PERCENTILES.items()},
        index=sims.columns,
    )


def actual_annual(firm_data: pd.DataFrame, firm: str, metric: str) -> pd.Series:
    s = firm_data[(firm, metric)].dropna()
    years = s.index.str[:4].astype(int)
    if metric == "aum":
        return s[s.index.str.endswith("Q4")].set_axis(years[s.index.str.endswith("Q4")])
    return s.groupby(years).sum()


# Runs -----------------------------------------------------------------------


def run_forecast(seed: int = SEED, n_sims: int = N_SIMS) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    drv, data = load_drivers(), load_firm_data()
    dmodel = fit_drivers(drv)
    quarters = future_quarters(HISTORY[1], HORIZON)
    drivers = simulate_drivers(dmodel, drv.loc[HISTORY[1]], len(quarters), n_sims, rng)

    rows, model_rows = [], []
    for firm in BANKS + FUND_MANAGERS:
        eqs = fit_firm(firm, data, drv, HISTORY)
        model_rows += equation_rows(firm, eqs)
        sims = annual(simulate_firm(firm, eqs, drivers, quarters, rng), quarters)
        for metric, table in sims.items():
            pct = percentiles(table)
            hist = actual_annual(data, firm, metric)
            for year, value in hist.items():
                rows.append({"firm": firm, "metric": metric, "year": year, "actual": value})
            for year, r in pct.iterrows():
                rows.append({"firm": firm, "metric": metric, "year": year, **r.to_dict()})

    market_years = annual({"market": np.exp(drivers["log_market"])}, quarters)["market"]
    rate_years = pd.DataFrame(
        {
            y: drivers["rate"][:, [i for i, q in enumerate(quarters) if q.startswith(str(y))]].mean(
                axis=1
            )
            for y in sorted({int(q[:4]) for q in quarters})
        }
    )
    last_market = float(np.exp(drv.loc[HISTORY[1], "log_market"]))
    mk = percentiles(market_years / 4 / last_market * 100)  # average level, 2025Q4 = 100
    rt = percentiles(rate_years)
    driver_table = mk.add_prefix("market_").join(rt.add_prefix("rate_"))
    driver_table.index.name = "year"

    settings = {
        "seed": seed,
        "simulations": n_sims,
        "block_quarters": BLOCK,
        "driver_window": "-".join(DRIVER_WINDOW),
        "history": "-".join(HISTORY),
        "horizon": HORIZON,
        "rate_long_run_mean": round(dmodel.rate_mean, 3),
        "rate_pull_per_quarter": round(dmodel.rate_speed, 4),
        # Average yearly growth of US market value over the driver window: the
        # middling scenario follows roughly this pace.
        "market_growth_per_year_history": round(
            float(np.exp(dmodel.shocks["market"].mean() * 4) - 1), 4
        ),
    }
    return {
        "forecast": pd.DataFrame(rows),
        "models": pd.DataFrame(model_rows),
        "drivers": driver_table.reset_index(),
        "settings": pd.Series(settings),
    }


def run_backtest(seed: int = SEED, n_sims: int = N_SIMS) -> pd.DataFrame:
    """Train on 2015-2020, predict 2021-2025: with real drivers and fully simulated."""
    rng = np.random.default_rng(seed + 1)
    drv, data = load_drivers(), load_firm_data()
    dmodel = fit_drivers(drv, (DRIVER_WINDOW[0], BACKTEST_TRAIN[1]))
    quarters = future_quarters(BACKTEST_TRAIN[1], BACKTEST_TEST[1])
    simulated = simulate_drivers(dmodel, drv.loc[BACKTEST_TRAIN[1]], len(quarters), n_sims, rng)
    real = {k: drv.loc[quarters, k].to_numpy()[None, :] for k in ("log_market", "rate", "log_vix")}

    rows = []
    for firm in BANKS + FUND_MANAGERS:
        eqs = fit_firm(firm, data, drv, BACKTEST_TRAIN)
        point = annual(
            simulate_firm(firm, eqs, real, quarters, rng, simulate_errors=False), quarters
        )
        sims = annual(simulate_firm(firm, eqs, simulated, quarters, rng), quarters)
        for metric in point:
            actual = actual_annual(data, firm, metric)
            pct = percentiles(sims[metric])
            for year in pct.index:
                rows.append(
                    {
                        "firm": firm,
                        "metric": metric,
                        "year": year,
                        "actual": actual.get(year),
                        "predicted_with_real_drivers": float(point[metric][year].iloc[0]),
                        **pct.loc[year].to_dict(),
                    }
                )
    df = pd.DataFrame(rows)
    df["error_pct"] = df["predicted_with_real_drivers"] / df["actual"] - 1
    df["inside_range"] = df["actual"].between(df["bad"], df["good"])
    return df


def equation_rows(firm: str, eqs: list[Equation]) -> list[dict]:
    rows = []
    for e in eqs:
        for term, value in e.coef.items():
            rows.append(
                {
                    "firm": firm,
                    "equation": e.name,
                    "term": term,
                    "coefficient": value,
                    "r2": e.r2,
                    "persistence": e.phi,
                    "quarters": e.n,
                }
            )
    return rows
