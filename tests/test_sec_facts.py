"""Quarterly figures from company facts: Q4 derivation and tag priority."""

from wallstreet import sec_facts as sf


def fact(start, end, val, filed="2016-02-20", form="10-K", accn="a"):
    row = {"end": end, "val": val, "accn": accn, "form": form, "filed": filed, "fy": 2015}
    if start:
        row["start"] = start
    return row


def company(tag, rows):
    return [{"facts": {"us-gaap": {tag: {"units": {"USD": rows}}}}}]


def test_q4_is_full_year_minus_three_quarters():
    docs = company(
        "Revenues",
        [
            fact("2015-01-01", "2015-03-31", 10, form="10-Q"),
            fact("2015-04-01", "2015-06-30", 20, form="10-Q"),
            fact("2015-07-01", "2015-09-30", 30, form="10-Q"),
            fact("2015-01-01", "2015-12-31", 100),
        ],
    )
    out = sf.discrete_quarters(sf.extract_facts(docs, "Revenues"))
    q4 = out.set_index("quarter").loc["2015Q4"]
    assert q4["value"] == 40
    assert q4["method"] == "derived_from_full_year"


def test_q4_from_nine_months_when_a_quarter_is_missing():
    docs = company(
        "Revenues",
        [
            fact("2015-07-01", "2015-09-30", 30, form="10-Q"),
            fact("2015-01-01", "2015-09-30", 60, form="10-Q"),
            fact("2015-01-01", "2015-12-31", 100),
        ],
    )
    out = sf.discrete_quarters(sf.extract_facts(docs, "Revenues")).set_index("quarter")
    assert out.loc["2015Q4", "value"] == 40
    assert out.loc["2015Q4", "method"] == "derived_from_nine_months"


def test_restated_value_replaces_original():
    docs = company(
        "Revenues",
        [
            fact("2015-01-01", "2015-03-31", 10, filed="2015-05-01", form="10-Q"),
            fact("2015-01-01", "2015-03-31", 12, filed="2016-05-01", form="10-Q"),
        ],
    )
    out = sf.discrete_quarters(sf.extract_facts(docs, "Revenues"))
    assert out.loc[0, "value"] == 12


def test_coalesce_prefers_first_tag():
    a = sf.discrete_quarters(
        sf.extract_facts(company("A", [fact("2015-01-01", "2015-03-31", 1, form="10-Q")]), "A")
    )
    b = sf.discrete_quarters(
        sf.extract_facts(
            company(
                "B",
                [
                    fact("2015-01-01", "2015-03-31", 9, form="10-Q"),
                    fact("2015-04-01", "2015-06-30", 2, form="10-Q"),
                ],
            ),
            "B",
        )
    )
    out = sf.coalesce([a, b]).set_index("quarter")
    assert out.loc["2015Q1", "tag"] == "A"
    assert out.loc["2015Q2", "tag"] == "B"


def test_instant_values_only_at_quarter_ends():
    docs = company(
        "Assets",
        [
            fact(None, "2015-03-31", 5, form="10-Q"),
            fact(None, "2015-02-14", 7, form="10-Q"),
        ],
    )
    out = sf.instant_quarters(sf.extract_facts(docs, "Assets"))
    assert list(out["quarter"]) == ["2015Q1"]


def test_ignores_non_periodic_forms():
    docs = company("Revenues", [fact("2015-01-01", "2015-03-31", 10, form="8-K")])
    assert sf.extract_facts(docs, "Revenues") == []
