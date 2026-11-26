"""13F information tables: units, options and aggregation."""

from datetime import date

from wallstreet import thirteenf as tf

XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass>
    <cusip>037833100</cusip><value>1000</value>
    <shrsOrPrnAmt><sshPrnamt>10</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass>
    <cusip>037833100</cusip><value>500</value>
    <shrsOrPrnAmt><sshPrnamt>5</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>EXXON MOBIL CORP</nameOfIssuer><titleOfClass>COM</titleOfClass>
    <cusip>30231g102</cusip><value>200</value>
    <shrsOrPrnAmt><sshPrnamt>2</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>EXXON MOBIL CORP</nameOfIssuer><titleOfClass>CALL</titleOfClass>
    <cusip>30231G102</cusip><value>999</value><putCall>Call</putCall>
    <shrsOrPrnAmt><sshPrnamt>1</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
</informationTable>
"""


def test_old_filings_are_in_thousands():
    rows = tf.parse_info_table(XML, filed=date(2022, 11, 14))
    assert rows["value_usd"].sum() == (1000 + 500 + 200) * 1000


def test_new_filings_are_in_dollars():
    rows = tf.parse_info_table(XML, filed=date(2023, 2, 14))
    assert rows["value_usd"].sum() == 1000 + 500 + 200


def test_options_are_dropped():
    rows = tf.parse_info_table(XML, filed=date(2023, 2, 14))
    assert len(rows) == 3


def test_aggregate_by_cusip_and_uppercase():
    rows = tf.parse_info_table(XML, filed=date(2023, 2, 14))
    sec = tf.aggregate_by_security(rows)
    assert list(sec["cusip"]) == ["037833100", "30231G102"]
    assert sec.loc[0, "value_usd"] == 1500
    assert sec.loc[0, "shares"] == 15


def test_summary_states_coverage():
    from wallstreet.edgar import Filing

    filing = Filing(1, "13F-HR", "x-1", date(2023, 2, 14), date(2022, 12, 31), "p.xml", "")
    sec = tf.aggregate_by_security(tf.parse_info_table(XML, filed=date(2023, 2, 14)))
    top, totals = tf.summarise("demo", date(2022, 12, 31), [filing], sec, top_n=1)
    assert len(top) == 1
    assert totals["top1_share"] == 1500 / 1700
    assert totals["positions"] == 2
