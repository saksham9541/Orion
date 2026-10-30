"""
Orion — RailRadar API client with multi-key round-robin rotation,
SQLAlchemy-backed budget tracking, caching, and offline snapshot fallback.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv
load_dotenv()

from backend.database import (
    get_api_cache,
    get_api_usage_count,
    get_engine,
    get_session,
    init_db,
    record_api_usage,
    set_api_cache,
)
from railopt.models import LiveTrainStatus

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.railradar.in/v1"
DEFAULT_KEY_LIMIT = 90
FAILING_COOLDOWN_SECONDS = 3600      # 1 hour penalty for 429 / 401 / 403
SERVER_ERROR_COOLDOWN_SECONDS = 300  # 5 minutes cooldown for 5xx / connection errors

# TTL constants in seconds
TTL_LIVE = 600              # 10 minutes for live status, station boards, exceptions
TTL_STATIC = 30 * 86400     # 30 days for timetable, route, delay, between stations


class RailRadarError(Exception):
    """Raised when a RailRadar API request fails or returns success=False."""
    pass


def mask_key(key: str) -> str:
    """Safely format a key showing only the last 4 characters."""
    if not key:
        return "none"
    return f"...{key[-4:]}"


def key_identifier(key: str) -> str:
    """Return short 8-char SHA256 hash of key for unambiguous database storage."""
    if not key:
        return ""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


class RailRadarClient:
    """
    Client for the RailRadar API v1 with:
    - Multi-key round-robin rotation with 1-hour penalty on failure/429 and 5-min on 5xx
    - Per-key monthly budget tracking in database (api_usage) using key SHA256 hashes
    - SQLAlchemy cache table (api_cache) with endpoint-appropriate TTLs
    - Offline fallback to data/railradar_snapshots/
    """

    def __init__(
        self,
        keys: Optional[list[str]] = None,
        base_url: Optional[str] = None,
        key_limit: Optional[int] = None,
        offline: Optional[bool] = None,
        snapshots_dir: Optional[str | Path] = None,
        db_engine: Any = None,
    ):
        if keys is None:
            raw_keys = os.environ.get("RAILRADAR_API_KEYS") or os.environ.get("RAILRADAR_API_KEY", "")
            collected_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
            if not collected_keys:
                for idx in range(1, 10):
                    k_env = os.environ.get(f"RAILRADAR_API_KEY_{idx}")
                    if k_env and k_env.strip():
                        collected_keys.append(k_env.strip())
            self.keys = collected_keys
        else:
            self.keys = [k.strip() for k in keys if k.strip()]

        self.base_url = (base_url or os.environ.get("RAILRADAR_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        
        limit_env = os.environ.get("RAILRADAR_KEY_LIMIT", str(DEFAULT_KEY_LIMIT))
        try:
            self.key_limit = key_limit if key_limit is not None else int(limit_env)
        except ValueError:
            self.key_limit = DEFAULT_KEY_LIMIT

        offline_env = os.environ.get("RAILRADAR_OFFLINE", "0").lower() in ("1", "true", "yes")
        self.offline = offline if offline is not None else offline_env

        self.snapshots_dir = Path(snapshots_dir or Path(__file__).resolve().parent.parent / "data" / "railradar_snapshots")
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        self._engine = db_engine or get_engine()
        init_db(self._engine)

        self._idx = 0
        self._failing_until: dict[str, float] = {}  # key -> timestamp until which key is blocked

    # ------------------------------------------------------------------
    # Key selection & budget helpers
    # ------------------------------------------------------------------

    def _get_year_month(self) -> str:
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")

    def get_budget_status(self) -> dict[str, Any]:
        """Return usage and budget status for all configured keys (showing last 4 chars only)."""
        ym = self._get_year_month()
        session = get_session(self._engine)
        try:
            status = {}
            for k in self.keys:
                ident = key_identifier(k)
                used = get_api_usage_count(session, ident, ym)
                remaining = max(0, self.key_limit - used)
                is_failing = time.time() < self._failing_until.get(k, 0)
                status[f"...{k[-4:]}"] = {
                    "used": used,
                    "remaining": remaining,
                    "limit": self.key_limit,
                    "failing": is_failing,
                    "failing_remaining_s": max(0, int(self._failing_until.get(k, 0) - time.time())) if is_failing else 0,
                }
            return {
                "year_month": ym,
                "offline": self.offline,
                "key_count": len(self.keys),
                "keys": status,
            }
        finally:
            session.close()

    def _select_next_key(self, tried_keys: Optional[set[str]] = None) -> tuple[Optional[str], Optional[str]]:
        """
        Round-robin across keys, skipping keys that:
        - have already been tried during this request (tried_keys)
        - have reached key_limit this calendar month
        - are currently marked failing (cooldown active)
        Returns (key, failure_reason) or (None, failure_reason)
        """
        if not self.keys:
            return None, "No API keys configured"

        tried = tried_keys or set()
        ym = self._get_year_month()
        now = time.time()
        session = get_session(self._engine)
        try:
            for _ in range(len(self.keys)):
                key = self.keys[self._idx]
                self._idx = (self._idx + 1) % len(self.keys)

                # Skip if already tried in this request
                if key in tried:
                    continue

                # Check failing penalty
                blocked_until = self._failing_until.get(key, 0)
                if now < blocked_until:
                    continue

                # Check monthly usage with 8-char hash
                ident = key_identifier(key)
                used = get_api_usage_count(session, ident, ym)
                if used >= self.key_limit:
                    logger.warning("RailRadar key %s has reached monthly limit (%d/%d)", mask_key(key), used, self.key_limit)
                    continue

                return key, None

            return None, "All keys are either rate-limited/failing, exhausted, or already tried in this request"
        finally:
            session.close()

    def _mark_key_failing(self, key: str, duration_seconds: float = FAILING_COOLDOWN_SECONDS):
        self._failing_until[key] = time.time() + duration_seconds
        logger.warning("RailRadar key %s marked failing for %.0fs", mask_key(key), duration_seconds)

    # ------------------------------------------------------------------
    # Offline snapshots
    # ------------------------------------------------------------------

    def _get_snapshot_path(self, path: str) -> Path:
        """Derive standard snapshot filename for an endpoint path."""
        p = path.strip("/").replace("/", "_")
        if p.startswith("trains_"):
            sub = p[len("trains_"):]
            return self.snapshots_dir / f"train_{sub}.json"
        elif p.startswith("stations_"):
            sub = p[len("stations_"):]
            return self.snapshots_dir / f"station_{sub}.json"
        return self.snapshots_dir / f"{p}.json"

    def _read_snapshot(self, path: str) -> dict:
        filepath = self._get_snapshot_path(path)
        candidates = [filepath]
        if "_timetable" not in filepath.name and "train_" in filepath.name and "_live" not in filepath.name and "_route" not in filepath.name and "_delay" not in filepath.name:
            candidates.append(filepath.with_name(filepath.stem + "_timetable.json"))

        for candidate in candidates:
            if candidate.exists():
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["source"] = "snapshot"
                    if "meta" in data and isinstance(data["meta"], dict):
                        data["meta"]["source"] = "snapshot"
                    return data
                except Exception as e:
                    logger.error("Failed to read snapshot file %s: %s", candidate, e)

        raise RailRadarError(
            f"Offline mode active or network unavailable, and no snapshot found for '{path}' at {filepath}"
        )

    # ------------------------------------------------------------------
    # Core request dispatcher (Cache -> Network -> Snapshot)
    # ------------------------------------------------------------------

    def _request(
        self,
        endpoint_path: str,
        params: Optional[dict] = None,
        ttl_seconds: int = TTL_LIVE,
    ) -> dict:
        """
        Execute an API call:
        1. Check database cache (api_cache).
        2. If cached and valid, return with source='cache'.
        3. If offline, read from snapshot with source='snapshot'.
        4. Select valid key, call API with Authorization: Bearer <key> (at most 1 try per key).
        5. Record usage in api_usage (using key SHA256 prefix), update cache, return with source='live'.
        6. On failure/exhaustion, fall back to snapshot or raise RailRadarError with last_error.
        """
        cache_key = endpoint_path
        if params:
            query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            cache_key = f"{endpoint_path}?{query}"

        # 1. Check Cache
        session = get_session(self._engine)
        try:
            cached = get_api_cache(session, cache_key)
            if cached and "data" in cached:
                res = {
                    "success": True,
                    "data": cached["data"],
                    "meta": cached.get("meta") or {},
                    "source": "cache",
                }
                res["meta"]["source"] = "cache"
                return res
        finally:
            session.close()

        # 2. Check Explicit Offline Mode
        if self.offline:
            logger.info("RailRadarClient in offline mode: reading snapshot for %s", endpoint_path)
            return self._read_snapshot(endpoint_path)

        # 3. Attempt network request with rotated keys (at most 1 try per key per request)
        tried_keys: set[str] = set()
        last_error = None

        while len(tried_keys) < len(self.keys):
            key, fail_reason = self._select_next_key(tried_keys=tried_keys)
            if not key:
                break

            tried_keys.add(key)
            url = f"{self.base_url}{endpoint_path}"
            headers = {
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
            }
            masked = mask_key(key)
            ident = key_identifier(key)
            session = get_session(self._engine)

            try:
                resp = requests.get(url, params=params, headers=headers, timeout=12)
                status_code = resp.status_code
                
                # Check for rate limiting (429)
                if status_code == 429:
                    retry_after = FAILING_COOLDOWN_SECONDS
                    if "Retry-After" in resp.headers:
                        try:
                            retry_after = float(resp.headers["Retry-After"])
                        except ValueError:
                            pass
                    record_api_usage(session, ident, endpoint_path, status_code, False)
                    self._mark_key_failing(key, retry_after)
                    last_error = f"HTTP 429 (Rate Limit) on key {masked}"
                    continue

                # Check for client error / bad request (400, 404, 422)
                if status_code in (400, 404, 422):
                    record_api_usage(session, ident, endpoint_path, status_code, False)
                    raise RailRadarError(f"Train or resource not found / bad request: {endpoint_path}")

                # Check for auth failure (401, 403)
                if status_code in (401, 403):
                    record_api_usage(session, ident, endpoint_path, status_code, False)
                    self._mark_key_failing(key, FAILING_COOLDOWN_SECONDS)
                    last_error = f"HTTP {status_code} (Auth error) on key {masked}"
                    continue

                # Check for server errors (5xx) -> 5 minute penalty
                if status_code >= 500:
                    record_api_usage(session, ident, endpoint_path, status_code, False)
                    self._mark_key_failing(key, SERVER_ERROR_COOLDOWN_SECONDS)
                    last_error = f"HTTP {status_code}: {resp.text[:200]}"
                    continue

                # Record request usage (other non-2xx status)
                if not resp.ok:
                    record_api_usage(session, ident, endpoint_path, status_code, False)
                    self._mark_key_failing(key, SERVER_ERROR_COOLDOWN_SECONDS)
                    last_error = f"HTTP {status_code}: {resp.text[:200]}"
                    continue

                # Successful call
                record_api_usage(session, ident, endpoint_path, status_code, True)
                raw = resp.json()
                if not isinstance(raw, dict) or not raw.get("success", False):
                    err_msg = raw.get("message") or raw.get("error") or "Unknown API error"
                    raise RailRadarError(f"RailRadar API error on {endpoint_path}: {err_msg}")

                # Save to cache
                data_payload = raw.get("data")
                meta_payload = raw.get("meta", {})
                set_api_cache(session, cache_key, endpoint_path, data_payload, meta_payload, ttl_seconds=ttl_seconds)

                raw["source"] = "live"
                if "meta" in raw and isinstance(raw["meta"], dict):
                    raw["meta"]["source"] = "live"
                return raw

            except requests.RequestException as e:
                # Network error (DNS, socket timeout, etc.) -> 5 min penalty
                record_api_usage(session, ident, endpoint_path, 0, False)
                self._mark_key_failing(key, SERVER_ERROR_COOLDOWN_SECONDS)
                last_error = f"Network error on key {masked}: {str(e)}"
                continue
            finally:
                session.close()

        # All available keys were tried once and failed
        logger.warning(
            "RailRadarClient: All keys tried for '%s' (last error: %s). Falling back to offline snapshots.",
            endpoint_path,
            last_error or "Keys unavailable",
        )
        try:
            return self._read_snapshot(endpoint_path)
        except Exception:
            err_detail = f" (last error: {last_error})" if last_error else ""
            raise RailRadarError(
                f"RailRadar request failed and no snapshot exists for '{endpoint_path}'{err_detail}"
            )

    # ------------------------------------------------------------------
    # Public API Endpoints (as specified in user prompt)
    # ------------------------------------------------------------------

    def get_train_timetable(self, train_number: str) -> dict:
        """GET /trains/{number} — Schedule and timetable (30-day cache)."""
        return self._request(f"/trains/{train_number}", ttl_seconds=TTL_STATIC)

    def get_train_live(self, train_number: str, date: Optional[str] = None) -> dict:
        """GET /trains/{number}/live — Live running status (10-minute cache)."""
        params = {"date": date} if date else None
        return self._request(f"/trains/{train_number}/live", params=params, ttl_seconds=TTL_LIVE)

    def get_train_route(self, train_number: str) -> dict:
        """GET /trains/{number}/route — Route geometry, GeoJSON (30-day cache)."""
        return self._request(f"/trains/{train_number}/route", ttl_seconds=TTL_STATIC)

    def get_train_delay(self, train_number: str) -> dict:
        """GET /trains/{number}/delay — Average delay and punctuality (30-day cache)."""
        return self._request(f"/trains/{train_number}/delay", ttl_seconds=TTL_STATIC)

    def get_station_live(self, station_code: str, hours: int = 2) -> dict:
        """GET /stations/{code}/live — Live station board (10-minute cache)."""
        params = {"hours": hours}
        return self._request(f"/stations/{station_code}/live", params=params, ttl_seconds=TTL_LIVE)

    def get_train_exceptions(self, exception_type: Optional[str] = None) -> dict:
        """GET /trains/exceptions — Active train exceptions (10-minute cache)."""
        params = {"type": exception_type} if exception_type else None
        return self._request("/trains/exceptions", params=params, ttl_seconds=TTL_LIVE)

    def get_trains_between(self, from_station: str, to_station: str, date: Optional[str] = None) -> dict:
        """GET /trains/between/{from}/{to} — Trains between two stations (30-day cache)."""
        params = {"date": date} if date else None
        return self._request(f"/trains/between/{from_station}/{to_station}", params=params, ttl_seconds=TTL_STATIC)

    # ------------------------------------------------------------------
    # Backwards compatibility helpers
    # ------------------------------------------------------------------

    def get_train_status(self, train_number: str) -> dict:
        """Backwards compatibility alias for get_train_live."""
        return self.get_train_live(train_number)

    def parse_live_status(self, raw: dict, corridor_id: str = "") -> LiveTrainStatus:
        """Parse raw response dict into LiveTrainStatus domain model."""
        data = raw.get("data", raw)
        train_info = data.get("train", {}) if isinstance(data, dict) else {}

        train_number = data.get("trainNumber") or train_info.get("number") or raw.get("train_number", "")
        train_name = data.get("trainName") or train_info.get("name") or raw.get("train_name", "")
        delay = float(data.get("delayMinutes", raw.get("delay_minutes", 0)))
        status_str = (data.get("status") or raw.get("status", "UNKNOWN")).upper()
        source_str = raw.get("source") or data.get("source") or "live"

        return LiveTrainStatus(
            train_number=str(train_number),
            train_name=str(train_name),
            corridor_id=corridor_id,
            delay_minutes=delay,
            status=status_str,
            last_updated=datetime.datetime.now(datetime.timezone.utc),
            source=source_str,
        )
