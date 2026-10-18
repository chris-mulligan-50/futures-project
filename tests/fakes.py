"""Test doubles for Databento, usable without a network or API key."""
import databento as db
import databento_dbn as dbn
import pandas as pd


def _ns(value) -> int:
    return pd.Timestamp(value, tz="UTC").value


def dbn_store(volume: int = 100, day: str = "2026-08-10") -> db.DBNStore:
    """A real DBN store holding one daily 6E bar."""
    metadata = dbn.Metadata(
        dataset="GLBX.MDP3",
        schema=dbn.Schema.OHLCV_1D,
        stype_in=dbn.SType.RAW_SYMBOL,
        stype_out=dbn.SType.INSTRUMENT_ID,
        start=_ns(day),
        end=_ns(pd.Timestamp(day) + pd.Timedelta(days=1)),
        symbols=["6EU6"],
        partial=[],
        not_found=[],
        mappings=[],
    )
    price = 1_160_500_000  # 1.1605, in units of 1e-9
    bar = dbn.OHLCVMsg(
        rtype=dbn.RType.OHLCV_1D,
        publisher_id=1,
        instrument_id=5510,
        ts_event=_ns(day),
        open=price,
        high=price,
        low=price,
        close=price,
        volume=volume,
    )
    return db.DBNStore.from_bytes(bytes(metadata.encode()) + bytes(bar))


class FakeClient:
    """Stands in for databento.Historical; records each request."""

    def __init__(self, volume: int = 100):
        self.requests = []
        self.timeseries = self
        self.volume = volume

    def get_range(self, **kwargs):
        self.requests.append(kwargs)
        return dbn_store(self.volume)
