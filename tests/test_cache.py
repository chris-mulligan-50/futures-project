import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from euro_roll import cache  # noqa: E402
from euro_roll.cache import cache_key, cache_path, load_or_download  # noqa: E402
from euro_roll.download import request_params  # noqa: E402
from fakes import dbn_store  # noqa: E402

PARAMS = request_params("ohlcv-1d", ["6EU6", "6EZ6"], "2026-08-10", "2026-09-15")


def test_symbol_order_and_duplicates_share_a_key():
    other = request_params(
        "ohlcv-1d", ["6EZ6", "6EU6", "6EZ6"], "2026-08-10", "2026-09-15"
    )
    assert cache_key(other) == cache_key(PARAMS)


def test_same_instant_in_another_time_zone_shares_a_key():
    utc = request_params("bbo-1m", ["6EU6"], "2026-09-08 15:00", "2026-09-08 15:01")
    chicago = request_params(
        "bbo-1m", ["6EU6"], "2026-09-08 10:00-05:00", "2026-09-08 10:01-05:00"
    )
    assert cache_key(chicago) == cache_key(utc)


@pytest.mark.parametrize(
    "changed",
    [
        dict(PARAMS, schema="bbo-1m"),
        dict(PARAMS, symbols=["6EU6"]),
        dict(PARAMS, start="2026-08-11T00:00:00+00:00"),
        dict(PARAMS, end="2026-09-16T00:00:00+00:00"),
        dict(PARAMS, stype_in="parent"),
        dict(PARAMS, dataset="XNAS.ITCH"),
    ],
)
def test_any_other_change_gets_its_own_key(changed):
    assert cache_key(changed) != cache_key(PARAMS)


def test_path_is_readable_and_grouped_by_dataset_and_schema(tmp_path):
    path = cache_path(PARAMS, tmp_path)
    assert path.parent == tmp_path / "GLBX.MDP3" / "ohlcv-1d"
    assert path.name == f"6EU6_6EZ6_20260810_20260915_{cache_key(PARAMS)}.dbn"


def test_path_drops_characters_unsafe_in_file_names(tmp_path):
    params = dict(PARAMS, symbols=["UD:1V: VT 2533938"])
    assert cache_path(params, tmp_path).name.startswith("UD_1V_VT_2533938_")


def test_default_cache_is_git_ignored():
    relative = cache.CACHE_DIR.relative_to(cache.REPO_ROOT)
    assert relative.parts[0] == "data"
    ignored = (cache.REPO_ROOT / ".gitignore").read_text().splitlines()
    assert "data/" in ignored


def test_miss_downloads_and_hit_reads_from_disk(tmp_path):
    calls = []

    def download():
        calls.append(1)
        return dbn_store(volume=7)

    first = load_or_download(PARAMS, download, tmp_path)
    second = load_or_download(PARAMS, download, tmp_path)
    assert len(calls) == 1
    assert cache_path(PARAMS, tmp_path).exists()
    assert second.to_df()["volume"].tolist() == first.to_df()["volume"].tolist() == [7]


def test_failed_download_leaves_no_cache_file(tmp_path):
    def download():
        raise ConnectionError("network down")

    with pytest.raises(ConnectionError):
        load_or_download(PARAMS, download, tmp_path)
    assert not any(tmp_path.rglob("*.dbn*"))


def test_interrupted_write_leaves_no_cache_file(tmp_path):
    class BrokenStore:
        def to_file(self, path):
            Path(path).write_bytes(b"half a file")
            raise OSError("disk full")

    with pytest.raises(OSError):
        load_or_download(PARAMS, BrokenStore, tmp_path)
    assert not any(tmp_path.rglob("*.dbn*"))
