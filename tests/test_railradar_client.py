"""
Unit tests for RailRadar client: envelope parsing, key rotation, monthly budgeting,
caching with TTLs, failing key cooldowns, and offline mode.
Never calls the real network.
"""
import datetime
import json
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine

from integrations.railradar_client import RailRadarClient, RailRadarError, mask_key, key_identifier
from backend.database import init_db, get_session, record_api_usage, set_api_cache


@pytest.fixture
def test_engine(tmp_path):
    """Isolated SQLite database for test runs."""
    db_file = tmp_path / "test_railradar.db"
    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine)
    return engine


@pytest.fixture
def mock_snapshots(tmp_path):
    """Temporary snapshot directory with dummy responses."""
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir()
    
    # Create a dummy train timetable snapshot
    timetable_data = {
        "success": True,
        "data": {
            "train": {"number": "12952", "name": "Mumbai Rajdhani"},
            "route": []
        },
        "meta": {"source": "test"}
    }
    with open(snap_dir / "train_12952_timetable.json", "w", encoding="utf-8") as f:
        json.dump(timetable_data, f)
        
    return snap_dir


def test_mask_key():
    assert mask_key("rg_dbb7250fefce448d8a2b904a0a09be14") == "...be14"
    assert mask_key("abcd1234") == "...1234"
    assert mask_key("") == "none"


def test_offline_mode_reads_snapshot(test_engine, mock_snapshots):
    client = RailRadarClient(
        keys=["key_dummy_1111"],
        offline=True,
        snapshots_dir=mock_snapshots,
        db_engine=test_engine,
    )
    result = client.get_train_timetable("12952")
    assert result["success"] is True
    assert result["data"]["train"]["number"] == "12952"
    assert result["source"] == "snapshot"


def test_cache_hit_avoids_network(test_engine, mock_snapshots):
    session = get_session(test_engine)
    # Pre-populate cache
    cached_payload = {"train": {"number": "12015", "name": "Ajmer Shatabdi"}}
    set_api_cache(
        session,
        cache_key="/trains/12015",
        endpoint="/trains/12015",
        data=cached_payload,
        meta={"source": "api"},
        ttl_seconds=3600,
    )
    session.close()

    client = RailRadarClient(
        keys=["key_dummy_1111"],
        offline=False,
        snapshots_dir=mock_snapshots,
        db_engine=test_engine,
    )

    with patch("requests.get") as mock_get:
        result = client.get_train_timetable("12015")
        mock_get.assert_not_called()
        assert result["success"] is True
        assert result["source"] == "cache"
        assert result["data"]["train"]["number"] == "12015"


def test_key_rotation_and_budget_skipping(test_engine, mock_snapshots):
    # key1 has exhausted limit (90 calls)
    session = get_session(test_engine)
    now_ym = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    ident_alpha = key_identifier("key_alpha_1111")
    for _ in range(90):
        record_api_usage(session, ident_alpha, "/trains/test", 200, True, year_month=now_ym)
    session.close()

    client = RailRadarClient(
        keys=["key_alpha_1111", "key_beta_2222"],
        key_limit=90,
        offline=False,
        snapshots_dir=mock_snapshots,
        db_engine=test_engine,
    )

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "data": {"train": {"number": "12301"}},
        "meta": {"source": "live"}
    }

    with patch("requests.get", return_value=mock_resp) as mock_get:
        res = client.get_train_timetable("12301")
        assert res["success"] is True
        # Ensure requests.get was called using key_beta_2222, skipping exhausted key_alpha_1111
        call_headers = mock_get.call_args[1]["headers"]
        assert call_headers["Authorization"] == "Bearer key_beta_2222"
        assert "x-api-key" not in call_headers


def test_failing_key_triggers_cooldown_and_rotates(test_engine, mock_snapshots):
    client = RailRadarClient(
        keys=["key_fail_3333", "key_good_4444"],
        key_limit=90,
        offline=False,
        snapshots_dir=mock_snapshots,
        db_engine=test_engine,
    )

    # First call returns 401 Unauthorized for key_fail_3333, second succeeds with key_good_4444
    resp_fail = MagicMock()
    resp_fail.ok = False
    resp_fail.status_code = 401
    resp_fail.text = "Unauthorized"

    resp_ok = MagicMock()
    resp_ok.ok = True
    resp_ok.status_code = 200
    resp_ok.json.return_value = {
        "success": True,
        "data": {"status": "RUNNING"},
        "meta": {"source": "live"}
    }

    with patch("requests.get", side_effect=[resp_fail, resp_ok]) as mock_get:
        res = client.get_train_live("12015")
        assert res["success"] is True
        assert res["source"] == "live"
        assert mock_get.call_count == 2
        # Verify key_fail_3333 is now in cooldown
        assert client._failing_until.get("key_fail_3333", 0) > 0


def test_envelope_error_raises_exception(test_engine, mock_snapshots):
    client = RailRadarClient(
        keys=["key_valid_5555"],
        offline=False,
        snapshots_dir=mock_snapshots,
        db_engine=test_engine,
    )

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": False,
        "message": "Invalid train number specified",
    }

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(RailRadarError, match="Invalid train number"):
            client.get_train_timetable("99999999")
