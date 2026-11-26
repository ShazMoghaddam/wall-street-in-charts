"""Checks that the findings text says what the data says.

The text in findings/build.py uses a few words that are not filled in from
the numbers ("nearly doubled", "tripled", "most", "while the others fell").
These tests fail if a data refresh makes any of those words untrue.
"""

import pytest

from wallstreet import charts as C
from wallstreet import findings as F
from wallstreet.config import PROCESSED

if not (PROCESSED / "fundamentals_quarterly.csv").exists():
    pytest.skip("processed data not built", allow_module_level=True)


@pytest.fixture(scope="module")
def n():
    return F.headline_numbers()


def test_jpmorgan_revenue_nearly_doubled(n):
    assert 1.8 <= n["jpmorgan_revenue_multiple"] < 2.0


def test_jpmorgan_bigger_than_the_other_four_combined(n):
    others = sum(n[f"{f}_revenue_2025_bn"] for f in F.LISTED if f != "jpmorgan")
    assert n["jpmorgan_revenue_2025_bn"] > others


def test_blackrock_aum_tripled(n):
    assert 2.9 <= n["blackrock_aum_2025q4"] / n["blackrock_aum_2015q4"] < 3.5


def test_blackrock_margin_narrowed(n):
    assert n["blackrock_revenue_multiple"] > n["blackrock_profit_multiple"]


def test_state_street_grew_slowest(n):
    multiples = {f: n[f"{f}_profit_multiple"] for f in F.LISTED}
    assert min(multiples, key=multiples.get) == "state_street"


def test_morgan_stanley_mostly_wealth(n):
    assert n["morgan_stanley_wealth_asset_management_share_2025"] > 0.5


def test_jpmorgan_profit_rose_while_others_fell(n):
    assert n["jpmorgan_profit_change_2021_2023_pct"] > 0
    for firm in ["goldman", "morgan_stanley", "blackrock", "state_street"]:
        assert n[f"{firm}_profit_change_2021_2023_pct"] < 0


def test_goldman_led_the_2022_fall(n):
    changes = {f: n[f"{f}_rates_change_pct"] for f in F.LISTED}
    assert min(changes, key=changes.get) == "goldman"


def test_rates_rose_from_near_zero(n):
    assert n["fed_funds_2021_avg"] < 0.25
    assert n["fed_funds_2023_avg"] > 4.5


def test_segment_shares_add_up():
    for firm in F.BANKS:
        assert F.segment_share(firm, 2025).sum() == pytest.approx(1.0)


def test_every_firm_has_its_own_colour():
    assert len(set(C.FIRM_COLOUR.values())) == len(C.FIRM_COLOUR)


def test_charts_build_in_both_themes():
    charts = C.build_all()
    assert len(charts) == 20
    for themes in charts.values():
        assert set(themes) == set(C.THEMES)
        assert str(themes["light"]) != str(themes["dark"])
