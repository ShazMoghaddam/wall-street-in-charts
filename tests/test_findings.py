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
    assert len(charts) == 31
    for themes in charts.values():
        assert set(themes) == set(C.THEMES)
        assert str(themes["light"]) != str(themes["dark"])


# Findings 3 to 6 --------------------------------------------------------------


def test_tech_is_the_largest_sector_and_grew(n):
    assert n["top_sector_2025"] == "Technology"
    assert n["tech_share_2025"] > 2 * n["tech_share_2015"]


def test_most_other_sectors_shrank(n):
    # "Most other sectors shrank": at most 3 of the 11 grew (tech plus two).
    assert n["sectors_grew"] <= 3


def test_they_follow_the_market(n):
    assert n["max_distance_2025"] < 0.05


def test_big_three_hold_slightly_more_tech_than_market(n):
    assert 0 < n["tech_share_2025"] - n["market_tech_share_2025"] < 0.05


def test_vanguard_real_estate_tilt_2015(n):
    assert n["vanguard_real_estate_2015"] > n["market_real_estate_2015"] + 0.02


def test_oil_gas_share_halved_for_everyone(n):
    for who in ["blackrock", "vanguard", "state_street", "market"]:
        assert n[f"{who}_oil_2025"] < 0.65 * n[f"{who}_oil_2015"]


def test_clean_energy_tiny_next_to_oil(n):
    assert n["clean_value_peak_bn"] < 0.1 * n["oil_value_2025_bn"]


def test_big_three_share_rose_to_almost_a_fifth(n):
    assert 0.15 < n["big_three_share_2025"] < 0.2
    assert n["big_three_share_2025"] > n["big_three_share_2015"]


def test_vanguard_largest_then_blackrock(n):
    assert (
        n["vanguard_market_share_2025"]
        > n["blackrock_market_share_2025"]
        > n["state_street_market_share_2025"]
    )


def test_median_stake_rose(n):
    assert n["median_stake_2025"] > n["median_stake_2015"]


def test_sector_weights_add_up():
    for who in ["big_three", "market", "vanguard"]:
        assert F.sector_weights(who).sum(axis=1).round(6).eq(1).all()
