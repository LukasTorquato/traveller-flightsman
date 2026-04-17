import json
from pathlib import Path

from traveller.models import Destination
from traveller.rotation import (
    load_rotation_state,
    next_intercontinental_selection,
    save_rotation_state,
)


def _asia():
    return [Destination(iata=c, city=c) for c in ("BKK", "HND", "SIN", "DEL", "KUL", "HKG", "CGK")]


def _sa():
    return [Destination(iata=c, city=c) for c in ("GRU", "GIG", "EZE", "BOG", "LIM")]


def test_rotation_first_run_starts_at_zero(tmp_path: Path):
    f = tmp_path / "rotation.json"
    state = load_rotation_state(f)
    assert state.asia_cursor == 0
    assert state.south_america_cursor == 0


def test_rotation_selects_next_three_asia_two_sa(tmp_path: Path):
    f = tmp_path / "rotation.json"
    state = load_rotation_state(f)
    sel, new_state = next_intercontinental_selection(
        state=state, asia=_asia(), south_america=_sa(),
        asia_pick=3, sa_pick=2,
    )
    assert [d.iata for d in sel.asia] == ["BKK", "HND", "SIN"]
    assert [d.iata for d in sel.south_america] == ["GRU", "GIG"]
    assert new_state.asia_cursor == 3
    assert new_state.south_america_cursor == 2


def test_rotation_wraps_around():
    from traveller.rotation import RotationState
    state = RotationState(asia_cursor=6, south_america_cursor=4)
    sel, new_state = next_intercontinental_selection(
        state=state, asia=_asia(), south_america=_sa(),
        asia_pick=3, sa_pick=2,
    )
    assert [d.iata for d in sel.asia] == ["CGK", "BKK", "HND"]
    assert [d.iata for d in sel.south_america] == ["LIM", "GRU"]
    assert new_state.asia_cursor == 2  # (6 + 3) % 7
    assert new_state.south_america_cursor == 1  # (4 + 2) % 5


def test_rotation_save_and_load_roundtrip(tmp_path: Path):
    from traveller.rotation import RotationState
    f = tmp_path / "rotation.json"
    save_rotation_state(RotationState(asia_cursor=5, south_america_cursor=3), f)
    loaded = load_rotation_state(f)
    assert loaded.asia_cursor == 5
    assert loaded.south_america_cursor == 3
    assert json.loads(f.read_text())["asia_cursor"] == 5
