"""
RailOpt — Re-export of RailRadarClient from integrations.railradar_client for backwards compatibility.
"""
from __future__ import annotations

from integrations.railradar_client import (
    RailRadarClient,
    RailRadarError,
    mask_key,
    DEFAULT_BASE_URL as RAILRADAR_BASE_URL,
)

__all__ = ["RailRadarClient", "RailRadarError", "mask_key", "RAILRADAR_BASE_URL"]