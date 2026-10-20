import io
import math

import pandas as pd
import pytest

from euro_roll import rates
from euro_roll.rates import (
    TENORS,
    build_rates,
    discount_to_continuous,
    forward_gap,
    load_rates,
    rate_gap,
    rates_on,
    read_series,
)

# Shaped like the real downloads: FRED leaves holidays empty (2010-12-24),
# and the ECB has no row on TARGET holidays.
FRED_CSV = {
    "DTB3": """observation_date,DTB3
2010-12-23,0.14
2010-12-24,
2010-12-27,0.17
2010-12-28,.
2010-12-29,0.13
""",
    "DTB6": """observation_date,DTB6
2010-12-23,0.19
2010-12-24,
2010-12-27,0.20
2010-12-28,.
2010-12-29,0.18
""",
}

ECB_CSV = {
    "SR_3M": """KEY,FREQ,TIME_PERIOD,OBS_VALUE,OBS_STATUS
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M,B,2010-12-23,0.50,A
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M,B,2010-12-24,0.51,A
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M,B,2010-12-28,0.52,A
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M,B,2010-12-29,0.53,A
""",
    "SR_6M": """KEY,FREQ,TIME_PERIOD,OBS_VALUE,OBS_STATUS
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_6M,B,2010-12-23,0.60,A
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_6M,B,2010-12-24,0.61,A
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_6M,B,2010-12-28,0.62,A
YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_6M,B,2010-12-29,0.63,A
""",
}


def fred(series="DTB3"):
    return read_series(io.StringIO(FRED_CSV[series]), "observation_date", series)


def ecb(series="SR_3M"):
    return read_series(io.StringIO(ECB_CSV[series]), "TIME_PERIOD", "OBS_VALUE")


def usd(discount_pct, tenor="3m"):
    return discount_to_continuous(discount_pct, TENORS[tenor].bill_days)


@pytest.fixture
def table():
    return build_rates(
        {"3m": fred("DTB3"), "6m": fred("DTB6")},
        {"3m": ecb("SR_3M"), "6m": ecb("SR_6M")},
    )


def curve(usd_3m, usd_6m, eur_3m, eur_6m):
    """Rates for 2020-03-05 only, so a 2020-03-06 snapshot uses them."""
    values = {"usd_3m": usd_3m, "usd_6m": usd_6m, "eur_3m": eur_3m, "eur_6m": eur_6m}
    index = pd.DatetimeIndex(["2020-03-05"], name="date")
    return pd.DataFrame({k: [v] for k, v in values.items()}, index=index)


DAY = pd.Timestamp("2020-03-06")


def test_read_series_drops_holidays():
    s = fred()
    assert list(s.index.strftime("%Y-%m-%d")) == ["2010-12-23", "2010-12-27", "2010-12-29"]
    assert s.iloc[0] == 0.14


def test_read_series_ignores_other_columns():
    s = ecb()
    assert len(s) == 4
    assert s["2010-12-28"] == 0.52


def test_discount_to_continuous_known_value():
    # 5% discount, 91 days: price 0.98736..., continuous rate 5.1018%.
    price = 1 - 0.05 * 91 / 360
    assert discount_to_continuous(5.0, 91) == pytest.approx(-math.log(price) * 365 / 91 * 100)
    assert discount_to_continuous(5.0, 91) == pytest.approx(5.1018, abs=1e-4)
    assert discount_to_continuous(0.0, 91) == 0.0


def test_build_rates_converts_each_bill_at_its_own_maturity(table):
    assert table.loc["2010-12-23", "usd_3m"] == pytest.approx(discount_to_continuous(0.14, 91))
    assert table.loc["2010-12-23", "usd_6m"] == pytest.approx(discount_to_continuous(0.19, 182))
    assert table.loc["2010-12-23", "eur_6m"] == 0.60


def test_build_rates_keeps_each_side_on_the_other_sides_holiday(table):
    # 2010-12-24: ECB has values, FRED does not.
    assert table.loc["2010-12-24", ["usd_3m", "usd_6m"]].isna().all()
    assert table.loc["2010-12-24", "eur_3m"] == 0.51


def test_rates_on_never_uses_the_same_day(table):
    # Both sides have values dated the 29th, published after the snapshot.
    out = rates_on(table, ["2010-12-29"]).iloc[0]
    assert out["usd_date"] == pd.Timestamp("2010-12-27")  # USD empty on the 28th
    assert out["eur_date"] == pd.Timestamp("2010-12-28")
    assert out["usd_6m"] == pytest.approx(usd(0.20, "6m"))
    assert out["gap_3m"] == pytest.approx(usd(0.17) - 0.52)


def test_rates_on_falls_back_over_each_sides_holidays(table):
    out = rates_on(table, ["2010-12-27", "2010-12-28"])
    dec27, dec28 = out.loc["2010-12-27"], out.loc["2010-12-28"]
    # Day before the 27th is the 26th: USD's latest is the 23rd, EUR's the 24th.
    assert dec27["usd_date"] == pd.Timestamp("2010-12-23")
    assert dec27["eur_date"] == pd.Timestamp("2010-12-24")
    # EUR has no value on the 27th either, so the 28th still uses the 24th.
    assert dec28["usd_date"] == pd.Timestamp("2010-12-27")
    assert dec28["eur_date"] == pd.Timestamp("2010-12-24")


def test_rates_on_ignores_time_of_day(table):
    out = rates_on(table, [pd.Timestamp("2010-12-24 10:00")])
    assert out["eur_date"].iloc[0] == pd.Timestamp("2010-12-23")


def test_rate_gap_sign_is_usd_minus_eur(table):
    assert rate_gap(table, "2010-12-30") == pytest.approx(usd(0.13) - 0.53)


def test_stale_or_missing_values_raise(table):
    with pytest.raises(ValueError):
        rate_gap(table, "2010-12-23")  # nothing before the data starts
    with pytest.raises(ValueError):
        rate_gap(table, "2011-01-10")  # last value is 12 days old
    assert math.isnan(rates_on(table, ["2011-01-10"])["gap_3m"].iloc[0])


def test_forward_gap_on_flat_curves_is_the_spot_gap():
    flat = curve(1.5, 1.5, 0.5, 0.5)
    gap = forward_gap(flat, DAY, "2020-03-16", "2020-06-15")
    assert gap == pytest.approx(1.0)
    assert gap == pytest.approx(rate_gap(flat, DAY))


def test_forward_gap_known_value():
    # Start 0.2 and end 0.4 years out. The 0.2-year rate is held at the
    # 3-month 1%; the 0.4-year rate interpolates to 1.6%. Forward:
    # (1.6 * 0.4 - 1 * 0.2) / 0.2 = 2.2%.
    start, end = DAY + pd.Timedelta(days=73), DAY + pd.Timedelta(days=146)
    assert forward_gap(curve(1.0, 2.0, 0.0, 0.0), DAY, start, end) == pytest.approx(2.2)
    assert forward_gap(curve(0.0, 0.0, 1.0, 2.0), DAY, start, end) == pytest.approx(-2.2)


@pytest.mark.parametrize("start, end", [
    ("2020-03-05", "2020-06-15"),  # starts before the day
    ("2020-06-15", "2020-06-15"),  # empty period
])
def test_forward_gap_rejects_bad_periods(start, end):
    with pytest.raises(ValueError):
        forward_gap(curve(1.0, 1.0, 0.0, 0.0), DAY, start, end)


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


def test_load_rates_replaces_a_cache_with_other_columns(table, tmp_path, monkeypatch):
    monkeypatch.setattr(rates, "download_rates", lambda start: table)
    path = tmp_path / "rates.csv"
    path.write_text("date,usd,eur\n2010-01-04,0.08,0.38\n")
    assert list(load_rates(path).columns) == list(table.columns)
    assert list(pd.read_csv(path, index_col="date").columns) == list(table.columns)
