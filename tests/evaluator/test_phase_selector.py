from traveller.evaluator.phase_selector import select_phase
from traveller.models import PhaseThresholds


def _th():
    return PhaseThresholds(phase1_max_obs=3, phase2_max_obs=11)


def test_phase_1_when_fewer_than_four():
    th = _th()
    for n in (0, 1, 2, 3):
        assert select_phase(observation_count=n, thresholds=th) == 1


def test_phase_2_between_four_and_eleven():
    th = _th()
    for n in (4, 5, 8, 11):
        assert select_phase(observation_count=n, thresholds=th) == 2


def test_phase_3_at_twelve_or_above():
    th = _th()
    for n in (12, 26, 104):
        assert select_phase(observation_count=n, thresholds=th) == 3
