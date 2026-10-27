"""
Test to verify prevention of RailRadar key burning on 5xx errors.
"""
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine

from integrations.railradar_client import RailRadarClient, RailRadarError
try:
    from integrations.railradar_client import key_identifier
except ImportError:
    key_identifier = lambda k: k[-4:]
from backend.database import init_db, get_session, get_api_usage_count


@pytest.fixture
def test_engine(tmp_path):
    db_file = tmp_path / "test_burn.db"
    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine)
    return engine


def test_500_error_does_not_burn_keys(test_engine, tmp_path):
    """
    Mock requests.get to always return 500 with 3 keys.
    Assert at most 3 network calls for one request, and the usage per key is 1 each.
    """
    keys = ["key_alpha_1111", "key_beta_2222", "key_gamma_3333"]
    client = RailRadarClient(
        keys=keys,
        offline=False,
        key_limit=10,
        snapshots_dir=tmp_path / "empty_snapshots",
        db_engine=test_engine,
    )

    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("requests.get", return_value=mock_resp) as mock_get:
        # Since no snapshots exist, it should raise RailRadarError after exhausting the 3 keys
        with pytest.raises(RailRadarError) as exc_info:
            client.get_train_live("12952")

        # 1. Assert at most 3 network calls were made (1 per key)
        assert mock_get.call_count <= 3, f"Expected at most 3 calls, but made {mock_get.call_count}"
        assert mock_get.call_count == 3, f"Expected exactly 3 calls (1 per key), but made {mock_get.call_count}"

        # 2. Assert usage per key is exactly 1 each
        session = get_session(test_engine)
        ym = client._get_year_month()
        for k in keys:
            # Check usage using identifier or suffix
            ident = k[-4:]
            try:
                from integrations.railradar_client import key_identifier
                ident = key_identifier(k)
            except ImportError:
                pass
            used = get_api_usage_count(session, ident, ym)
            assert used == 1, f"Expected key {k} usage to be 1, but got {used}"
        session.close()

        # 3. Assert error message contains the last error
        assert "500" in str(exc_info.value)
