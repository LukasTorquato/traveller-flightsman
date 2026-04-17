from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from traveller.models import Destination


@dataclass(frozen=True)
class RotationState:
    asia_cursor: int = 0
    south_america_cursor: int = 0


@dataclass(frozen=True)
class IntercontinentalSelection:
    asia: list[Destination]
    south_america: list[Destination]


def load_rotation_state(path: Path) -> RotationState:
    if not path.is_file():
        return RotationState()
    data = json.loads(path.read_text(encoding="utf-8"))
    return RotationState(
        asia_cursor=int(data.get("asia_cursor", 0)),
        south_america_cursor=int(data.get("south_america_cursor", 0)),
    )


def save_rotation_state(state: RotationState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")


def _take(items: list[Destination], start: int, count: int) -> list[Destination]:
    if not items or count <= 0:
        return []
    out: list[Destination] = []
    n = len(items)
    for i in range(count):
        out.append(items[(start + i) % n])
    return out


def next_intercontinental_selection(
    *,
    state: RotationState,
    asia: list[Destination],
    south_america: list[Destination],
    asia_pick: int = 3,
    sa_pick: int = 2,
) -> tuple[IntercontinentalSelection, RotationState]:
    asia_sel = _take(asia, state.asia_cursor, asia_pick)
    sa_sel = _take(south_america, state.south_america_cursor, sa_pick)
    new_asia_cursor = (state.asia_cursor + asia_pick) % max(1, len(asia))
    new_sa_cursor = (state.south_america_cursor + sa_pick) % max(1, len(south_america))
    return (
        IntercontinentalSelection(asia=asia_sel, south_america=sa_sel),
        RotationState(asia_cursor=new_asia_cursor, south_america_cursor=new_sa_cursor),
    )
