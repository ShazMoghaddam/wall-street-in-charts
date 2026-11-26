"""Segments, AUM, FRED and secret handling."""

from datetime import date

import pandas as pd
import pytest

from wallstreet import aum, fred, segments
from wallstreet.config import MissingSecretError, require_env
from wallstreet.edgar import Filing
from wallstreet.http import cache_key, redact

SEGMENT_XML = b"""<?xml version="1.0"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
      xmlns:us-gaap="http://fasb.org/us-gaap/2024"
      xmlns:srt="http://fasb.org/srt/2024">
  <context id="seg">
    <entity><identifier scheme="x">1</identifier><segment>
      <xbrldi:explicitMember dimension="srt:ConsolidationItemsAxis">us-gaap:OperatingSegmentsMember</xbrldi:explicitMember>
      <xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">ms:WealthManagementSegmentMember</xbrldi:explicitMember>
    </segment></entity>
    <period><startDate>2024-01-01</startDate><endDate>2024-12-31</endDate></period>
  </context>
  <context id="region">
    <entity><identifier scheme="x">1</identifier><segment>
      <xbrldi:explicitMember dimension="srt:StatementGeographicalAxis">srt:AsiaMember</xbrldi:explicitMember>
    </segment></entity>
    <period><startDate>2024-01-01</startDate><endDate>2024-12-31</endDate></period>
  </context>
  <context id="quarter">
    <entity><identifier scheme="x">1</identifier><segment>
      <xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">ms:WealthManagementSegmentMember</xbrldi:explicitMember>
    </segment></entity>
    <period><startDate>2024-10-01</startDate><endDate>2024-12-31</endDate></period>
  </context>
  <us-gaap:RevenuesNetOfInterestExpense contextRef="seg" unitRef="usd">28000</us-gaap:RevenuesNetOfInterestExpense>
  <us-gaap:RevenuesNetOfInterestExpense contextRef="region" unitRef="usd">5000</us-gaap:RevenuesNetOfInterestExpense>
  <us-gaap:RevenuesNetOfInterestExpense contextRef="quarter" unitRef="usd">7000</us-gaap:RevenuesNetOfInterestExpense>
</xbrl>
"""


def test_segment_parser_keeps_full_year_segment_totals_only():
    filing = Filing(1, "10-K", "a-1", date(2025, 2, 20), date(2024, 12, 31), "x.htm", "")
    df = segments.parse_segments(SEGMENT_XML, "morgan_stanley", filing)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["segment_member"] == "WealthManagementSegmentMember"
    assert row["metric"] == "revenue"
    assert row["value_usd"] == 28000


def test_segment_member_rules():
    axis = segments.SEGMENT_AXIS
    assert segments.segment_member([(axis, "x:A")]) == "x:A"
    ops = ("us-gaap:ConsolidationItemsAxis", "us-gaap:OperatingSegmentsMember")
    assert segments.segment_member([ops, (axis, "x:A")]) == "x:A"
    elim = ("srt:ConsolidationItemsAxis", "us-gaap:IntersegmentEliminationMember")
    assert segments.segment_member([elim, (axis, "x:A")]) is None
    assert segments.segment_member([("srt:StatementGeographicalAxis", "srt:AsiaMember")]) is None


def test_latest_10k_wins_for_each_year():
    old = pd.DataFrame(
        [
            {
                "firm": "f",
                "year": 2020,
                "metric": "revenue",
                "segment_member": "Old",
                "value_usd": 1,
                "report_year": 2020,
            }
        ]
    )
    new = pd.DataFrame(
        [
            {
                "firm": "f",
                "year": 2020,
                "metric": "revenue",
                "segment_member": "New",
                "value_usd": 2,
                "report_year": 2022,
            }
        ]
    )
    out = segments.latest_per_year([old, new])
    assert list(out["segment_member"]) == ["New"]


def test_find_aum_in_millions_and_billions():
    blk = "BlackRock ... Assets under management $ 10,645,721 up 15%"
    stt = "AUC/A $ 46.6 trillion; AUM ($B) $ 4,415"
    assert aum.find_aum(blk, aum.RULES["blackrock"]) == pytest.approx(10.645721)
    assert aum.find_aum(stt, aum.RULES["state_street"]) == pytest.approx(4.415)


def test_find_aum_skips_numbers_out_of_range():
    text = "AUM growth of 1,200 basis points ... AUM $ 4,774,192"
    assert aum.find_aum(text, aum.RULES["blackrock"]) == pytest.approx(4.774192)


def test_previous_quarter_end():
    assert aum.previous_quarter_end(date(2016, 1, 15)) == date(2015, 12, 31)
    assert aum.previous_quarter_end(date(2016, 4, 14)) == date(2016, 3, 31)
    assert aum.previous_quarter_end(date(2016, 7, 14)) == date(2016, 6, 30)
    assert aum.previous_quarter_end(date(2016, 10, 18)) == date(2016, 9, 30)


def test_fred_drops_missing_values_and_builds_quarters():
    payload = {
        "observations": [
            {"date": "2020-01-02", "value": "1.5"},
            {"date": "2020-01-03", "value": "."},
            {"date": "2020-03-31", "value": "2.5"},
        ]
    }
    daily = fred.parse_observations("DFF", payload)
    assert len(daily) == 2
    q = fred.to_quarterly(daily)
    assert q.loc[0, "quarter"] == "2020Q1"
    assert q.loc[0, "mean"] == 2.0
    assert q.loc[0, "last"] == 2.5


def test_api_key_never_reaches_cache_paths():
    url = "https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key=SECRET"
    assert "SECRET" not in redact(url)
    assert "SECRET" not in cache_key(url)


def test_missing_secret_has_clear_message(monkeypatch):
    monkeypatch.delenv("NOT_A_REAL_VAR", raising=False)
    with pytest.raises(MissingSecretError, match="NOT_A_REAL_VAR"):
        require_env("NOT_A_REAL_VAR", "Add it to .env.")


def test_unit_slips_are_fixed_or_dropped():
    from wallstreet import market13f

    info = pd.DataFrame(
        {
            "cusip": ["A", "A", "A", "A"],
            "value_usd": [100_000.0, 100_000_000.0, 100.0, 500_000.0],
            "shares": [1000, 1000, 1000, 1000],
            "SSHPRNAMTTYPE": ["SH", "SH", "SH", "SH"],
        }
    )
    ref_price = pd.Series({"A": 100.0})
    ref_shares = pd.Series({"A": 10_000})
    kept, stats = market13f.reconcile_units(info, ref_price, ref_shares)
    # Right, 1,000x too big (fixed), 1,000x too small (fixed), 5x off (dropped)
    assert kept["value_usd"].tolist() == [100_000.0, 100_000.0, 100_000.0]
    assert stats["rows_rescaled"] == 2
    assert stats["rows_dropped_off_price"] == 1


def test_sector_mapping_rules():
    from wallstreet import sectors

    assert sectors.sic_to_sector(2834) == "Health care"  # narrow range beats chemicals
    assert sectors.sic_to_sector(4922) == "Energy"  # pipelines beat utilities
    assert sectors.sic_to_sector(5331) == "Consumer staples"
    assert sectors.normalise("QUALCOMM INC/DE") == sectors.normalise("Qualcomm Inc")
    assert sectors.is_fund("ISHARES TR", "CORE S&P 500 ETF")
    assert not sectors.is_fund("APPLE INC", "COM")
    assert sectors.clean_energy_name("FIRST SOLAR INC") == "First Solar"
    assert sectors.clean_energy_name("NEXTERA ENERGY INC") is None
