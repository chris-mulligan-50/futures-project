import io
import math

import pandas as pd
import pytest

from euro_roll import rates
from euro_roll.rates import (
    build_rates,
    discount_to_continuous,
    load_rates,
    parse_ecb,
    parse_fred,
    rate_gap,
    rates_on,
)

# Shaped like the real downloads: FRED leaves holidays empty (2010-12-24),
# and the ECB has no row on TARGET holidays.
FRED_CSV = """observation_date,DTB3
2010-12-23,0.14
2010-12-24,
2010-12-27,0.17
2010-12-28,.
2010-12-29,0.13
"""

ECB_CSV = """KEY,FREQ,TIME_PERIOD,OBS_VALUE,OBS_STATUS
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M,B,2010-12-23,0.50,A
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M,B,2010-12-24,0.51,A
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M,B,2010-12-28,0.52,A
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M,B,2010-12-29,0.53,A
"""


@pytest.fixture
def table():
    return build_rates(parse_fred(io.StringIO(FRED_CSV)), parse_ecb(io.StringIO(ECB_CSV)))


def test_parse_fred_drops_holidays():
    s = parse_fred(io.StringIO(FRED_CSV))
    assert list(s.index.strftime("%Y-%m-%d")) == ["2010-12-23", "2010-12-27", "2010-12-29"]
    assert s.iloc[0] == 0.14


def test_parse_ecb_reads_values():
    s = parse_ecb(io.StringIO(ECB_CSV))
    assert len(s) == 4
    assert s["2010-12-28"] == 0.52


def test_discount_to_continuous_known_value():
    # 5% discount, 91 days: price 0.98736..., continuous rate 5.1018%.
    price = 1 - 0.05 * 91 / 360
    assert discount_to_continuous(5.0) == pytest.approx(-math.log(price) * 365 / 91 * 100)
    assert discount_to_continuous(5.0) == pytest.approx(5.1018, abs=1e-4)
    assert discount_to_continuous(0.0) == 0.0


def test_build_rates_keeps_each_side_on_the_other_sides_holiday(table):
    # 2010-12-24: ECB has a value, FRED does not.
    assert math.isnan(table.loc["2010-12-24", "usd"])
    assert table.loc["2010-12-24", "eur"] == 0.51
    assert table.loc["2010-12-23", "usd"] == pytest.approx(discount_to_continuous(0.14))


def test_rates_on_uses_each_legs_latest_earlier_value(table):
    out = rates_on(table, ["2010-12-24", "2010-12-27"])
    dec24, dec27 = out.loc["2010-12-24"], out.loc["2010-12-27"]
    # USD missing on the 24th: falls back to the 23rd.
    assert dec24["usd_date"] == pd.Timestamp("2010-12-23")
    assert dec24["eur_date"] == pd.Timestamp("2010-12-24")
    # EUR missing on the 27th: falls back to the 24th.
    assert dec27["usd_date"] == pd.Timestamp("2010-12-27")
    assert dec27["eur_date"] == pd.Timestamp("2010-12-24")
    assert dec27["gap"] == pytest.approx(discount_to_continuous(0.17) - 0.51)


def test_rates_on_ignores_time_of_day(table):
    out = rates_on(table, [pd.Timestamp("2010-12-23 10:00")])
    assert out["usd_date"].iloc[0] == pd.Timestamp("2010-12-23")


def test_rate_gap_sign_is_usd_minus_eur(table):
    assert rate_gap(table, "2010-12-29") == pytest.approx(
        discount_to_continuous(0.13) - 0.53
    )


def test_stale_or_missing_values_raise(table):
    with pytest.raises(ValueError):
        rate_gap(table, "2010-12-22")  # before the data starts
    with pytest.raises(ValueError):
        rate_gap(table, "2011-01-10")  # last value is 12 days old
    assert math.isnan(rates_on(table, ["2011-01-10"])["gap"].iloc[0])


def test_load_rates_downloads_once_then_reads_cache(table, tmp_path, monkeypatch):
    calls = []

    def fake_download(start):
        calls.append(start)
        return table

    monkeypatch.setattr(rates, "download_rates", fake_download)
    path = tmp_path / "rates.csv"
    first = load_rates(path)
    second = load_rates(path)
    assert len(calls) == 1
    assert not (tmp_path / "rates.csv.partial").exists()
    pd.testing.assert_frame_equal(second, first, check_freq=False)
    load_rates(path, refresh=True)
    assert len(calls) == 2
