"""
traffic/train_weights.py

Shared train type priority weights for delay cascading, impact scoring,
and optimization in Orion.
Used consistently by traffic/window_reliability.py, optimizer/cpsat_solver.py,
and simulator/block_impact_simulator.py.
"""
from __future__ import annotations

from typing import Dict, Union
from railopt.models import TrainType

# Train priority / disruption cost weights relative to standard passenger train (1.0)
TRAIN_TYPE_PRIORITY_WEIGHTS: Dict[TrainType, float] = {
    TrainType.RAJDHANI: 2.5,
    TrainType.SHATABDI: 2.2,
    TrainType.VANDE_BHARAT: 2.0,
    TrainType.DURONTO: 2.0,
    TrainType.GARIB_RATH: 1.6,
    TrainType.SUPERFAST: 1.5,
    TrainType.MAIL_EXPRESS: 1.2,
    TrainType.PASSENGER: 1.0,
    TrainType.SUBURBAN: 1.0,
    TrainType.FREIGHT: 0.8,
    TrainType.MILITARY: 2.5,
}


def get_train_type_weight(train_type: Union[TrainType, str, None]) -> float:
    """Return priority weight for train type, defaulting to 1.0 for unknown types."""
    if train_type is None:
        return 1.0
    if isinstance(train_type, str):
        try:
            tt = TrainType(train_type.upper())
            return TRAIN_TYPE_PRIORITY_WEIGHTS.get(tt, 1.0)
        except Exception:
            return 1.0
    return TRAIN_TYPE_PRIORITY_WEIGHTS.get(train_type, 1.0)
