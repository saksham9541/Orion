import pytest
from unittest.mock import MagicMock
from integrations.railradar_client import RailRadarClient, RailRadarError


def test_404_does_not_disable_keys_and_stops_retrying(tmp_path, monkeypatch):
    """
    Test Step 1: 404/400/422 responses:
    - Record usage
    - Do NOT mark key as failing
    - Do NOT try other keys (makes exactly 1 call)
    - Raises RailRadarError
    - Next valid request succeeds
    """
    db_file = tmp_path / "test_404.db"
    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{db_file}")
    client = RailRadarClient(
        keys=["key_alpha_1234", "key_beta_5678", "key_gamma_9012"],
        offline=False,
        db_engine=engine,
    )

    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 404
        resp.text = "Not Found"
        return resp

    monkeypatch.setattr("requests.get", mock_get)

    with pytest.raises(RailRadarError) as exc_info:
        client.get_train_timetable("99999")

    assert "Train or resource not found / bad request" in str(exc_info.value)
    # Exactly 1 network call must be made
    assert call_count == 1, f"Expected 1 call, but made {call_count}"

    # No key should be marked as failing
    for k in client.keys:
        assert client._failing_until.get(k, 0) == 0, f"Key {k} was marked as failing"

    # Next valid request must succeed
    def mock_get_200(*args, **kwargs):
        resp = MagicMock()
        resp.ok = True
        resp.status_code = 200
        resp.json.return_value = {
            "success": True,
            "data": {"trainNumber": "12015"},
            "meta": {"source": "live"},
        }
        return resp

    monkeypatch.setattr("requests.get", mock_get_200)
    valid_resp = client.get_train_timetable("12015")
    assert valid_resp["data"]["trainNumber"] == "12015"


def test_key_cooldown_expiry_works_without_restart(tmp_path, monkeypatch):
    """When a key's cooldown timestamp passes, it must automatically become eligible again."""
    import time
    from sqlalchemy import create_engine
    db_file = tmp_path / "test_cooldown.db"
    engine = create_engine(f"sqlite:///{db_file}")
    client = RailRadarClient(
        keys=["key_single_1234"],
        offline=False,
        db_engine=engine,
    )

    fake_now = 1000.0
    monkeypatch.setattr(time, "time", lambda: fake_now)

    # Mark key failing for 5 minutes (300s)
    client._mark_key_failing("key_single_1234", duration_seconds=300)
    assert client._failing_until["key_single_1234"] == 1300.0

    # While fake_now is 1000, key should be skipped
    key, reason = client._select_next_key()
    assert key is None
    assert "failing" in reason

    # Advance time past cooldown
    fake_now = 1301.0
    key, reason = client._select_next_key()
    assert key == "key_single_1234"
    assert reason is None

