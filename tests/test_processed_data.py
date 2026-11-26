"""Checks on the committed data in data/processed/.

These run in CI without network access. They catch the mistakes that matter
most for the report: missing or duplicated quarters, unit slips (thousands vs
dollars), and broken joins such as BlackRock's change of SEC ID.
"""

import pandas as pd
import pytest

from wallstreet.config import PROCESSED, load_settings

SETTINGS = load_settings()
YEARS = range(SETTINGS.start.year, SETTINGS.end.year + 1)
QUARTERS = [f"{y}Q{q}" for y in YEARS for q in range(1, 5)]
QUARTER_ENDS = (
    pd.period_range(f"{SETTINGS.start.year}Q1", f"{SETTINGS.end.year}Q4", freq="Q")
    .to_timestamp(how="end")
    .strftime("%Y-%m-%d")
    .tolist()
)
LISTED = [k for k, f in SETTINGS.firms.items() if f.files_results]
FUND_13F = [k for k, f in SETTINGS.firms.items() if f.thirteenf_cik]


def load(name):
    path = PROCESSED / name
    if not path.exists():
        pytest.skip(f"{name} not built yet")
    return pd.read_csv(path, dtype={"cusip": str})


@pytest.fixture(scope="module")
def fundamentals():
    return load("fundamentals_quarterly.csv")


@pytest.mark.parametrize("metric", ["revenue", "net_income", "total_assets"])
def test_every_listed_firm_has_every_quarter(fundamentals, metric):
    df = fundamentals[fundamentals["metric"] == metric]
    for firm in LISTED:
        quarters = df[df["firm"] == firm]["quarter"].tolist()
        assert quarters == QUARTERS, f"{firm} {metric} has gaps or extras"


def test_no_duplicate_rows(fundamentals):
    assert not fundamentals.duplicated(["firm", "metric", "quarter"]).any()


def test_revenue_and_assets_are_positive(fundamentals):
    df = fundamentals[fundamentals["metric"].isin(["revenue", "total_assets"])]
    assert (df["value_usd"] > 0).all()


def test_known_annual_figures(fundamentals):
    """Spot checks against published annual results ($ billions, rounded)."""
    df = fundamentals.assign(year=fundamentals["quarter"].str[:4])
    annual = df[df["metric"] == "revenue"].groupby(["firm", "year"])["value_usd"].sum() / 1e9
    assert annual["jpmorgan", "2015"] == pytest.approx(93.5, abs=0.2)
    assert annual["goldman", "2015"] == pytest.approx(33.8, abs=0.2)
    assert annual["blackrock", "2015"] == pytest.approx(11.4, abs=0.2)


def test_fred_series_cover_the_period():
    q = load("fred_quarterly.csv")
    for series in SETTINGS.fred_series:
        quarters = set(q[q["series"] == series]["quarter"])
        expected = set(QUARTERS)
        if series == "SP500":  # FRED only shares the last ten years
            expected = {x for x in expected if x >= "2017Q1"}
        assert expected <= quarters, f"{series} is missing quarters"


def test_aum_has_every_quarter_and_no_jumps():
    df = load("aum.csv")
    for firm in ["blackrock", "state_street"]:
        s = df[df["firm"] == firm].sort_values("as_of")
        assert s["as_of"].tolist() == QUARTER_ENDS
        change = s["aum_trillion_usd"].pct_change().abs().dropna()
        assert change.max() < 0.2, f"{firm} AUM jumps more than 20% in a quarter"


def test_holdings_every_quarter_and_steady_totals():
    t = load("holdings_13f_totals.csv")
    for firm in FUND_13F:
        s = t[t["firm"] == firm].sort_values("quarter_end")
        assert s["quarter_end"].tolist() == QUARTER_ENDS
        change = s["total_value_usd"].pct_change().abs().dropna()
        # A jump this big would mean a unit slip or a missing filing.
        assert change.max() < 0.3, f"{firm} 13F total jumps more than 30% in a quarter"


def test_blackrock_join_has_no_gap_or_overlap():
    t = load("holdings_13f_totals.csv")
    s = t[t["firm"] == "blackrock"].set_index("quarter_end")
    assert s.loc["2024-06-30", "filer_cik"] == "1364742"
    assert s.loc["2024-09-30", "filer_cik"] == "2012383"
    assert (s.loc["2015-03-31":"2016-12-31", "filings"] == 7).all()


def test_top_holdings_cover_most_of_the_value():
    t = load("holdings_13f_totals.csv")
    assert (t["top500_share"] >= 0.65).all()


def test_bank_segments_are_mapped():
    s = load("bank_segments_annual.csv")
    assert s["bucket"].notna().all()
    revenue = s[(s["metric"] == "revenue") & ~s["bucket"].isin(["detail", "exclude"])]
    for firm in ["jpmorgan", "goldman", "morgan_stanley"]:
        years = set(revenue[revenue["firm"] == firm]["year"])
        assert years == set(range(SETTINGS.start.year, SETTINGS.end.year + 1)), firm


def test_sector_coverage_is_high():
    df = load("holdings_by_sector.csv")
    total = df.groupby(["firm", "quarter_end"])["value_usd"].sum()
    mapped = df[df["sector"] != "Not mapped"].groupby(["firm", "quarter_end"])["value_usd"].sum()
    assert (mapped / total).min() > 0.9


def test_market_every_year_end():
    m = load("market_summary.csv")
    assert m["year"].tolist() == list(YEARS)
    # The cleaned institutional market sits below the total US market value.
    fred = load("fred_quarterly.csv")
    z = fred[fred["series"] == "BOGZ1LM883164115Q"].set_index("quarter")["last"] * 1e6
    for row in m.itertuples():
        assert 0.5 < row.total_value_usd / z[f"{row.year}Q4"] < 1.0


def test_stakes_are_plausible():
    s = load("big_three_stakes.csv").dropna(subset=["stake"])
    assert s["stake"].between(0, 0.6).all()
    assert s.groupby("quarter_end")["stake"].count().min() > 400


def test_clean_energy_list_matches_names():
    c = load("clean_energy_matches.csv")
    assert c["company"].nunique() >= 25
