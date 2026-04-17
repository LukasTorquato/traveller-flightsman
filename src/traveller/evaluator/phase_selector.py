from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from traveller.models import PhaseThresholds

Phase = Literal[1, 2, 3]


def select_phase(*, observation_count: int, thresholds: PhaseThresholds) -> Phase:
    if observation_count <= thresholds.phase1_max_obs:
        return 1
    if observation_count <= thresholds.phase2_max_obs:
        return 2
    return 3
