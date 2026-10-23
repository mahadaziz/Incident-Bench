import pytest

from scenarios.loader import DEV_DIR, load_dir
from scenarios.schema import RootCause, Scenario

SEEDS = load_dir(DEV_DIR)


def test_seed_scenarios_validate() -> None:
    by_difficulty = {s.difficulty: s.ground_truth.root_cause for s in SEEDS}

    assert len(SEEDS) == 3
    assert by_difficulty == {
        1: RootCause.CONFIG_ERROR,
        2: RootCause.DEPENDENCY_SLOWDOWN,
        3: RootCause.CERT_EXPIRY,
    }


@pytest.mark.parametrize("scenario", SEEDS, ids=lambda s: s.id)
def test_seed_agent_view_leaks_nothing_hidden(scenario: Scenario) -> None:
    dumped = scenario.agent_view().model_dump_json()

    for secret in [scenario.id, scenario.title, scenario.ground_truth.summary]:
        assert secret not in dumped


@pytest.mark.parametrize("scenario", SEEDS, ids=lambda s: s.id)
def test_seed_has_distractors(scenario: Scenario) -> None:
    assert scenario.ground_truth.distractors
