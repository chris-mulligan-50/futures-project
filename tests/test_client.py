import sys
from pathlib import Path

import databento as db
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from euro_roll import client  # noqa: E402
from euro_roll.client import ENV_VAR, get_client  # noqa: E402

FAKE_KEY = "db-" + "x" * 29  # right shape; never sent anywhere


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_key_raises_clear_error(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(ENV_VAR, value)
    with pytest.raises(RuntimeError, match=ENV_VAR):
        get_client()


def test_returns_historical_client(monkeypatch):
    monkeypatch.setenv(ENV_VAR, FAKE_KEY)
    assert isinstance(get_client(), db.Historical)


def test_strips_whitespace_around_key(monkeypatch):
    seen = []
    monkeypatch.setattr(client.db, "Historical", lambda key: seen.append(key))
    monkeypatch.setenv(ENV_VAR, f"  {FAKE_KEY}\n")
    get_client()
    assert seen == [FAKE_KEY]
