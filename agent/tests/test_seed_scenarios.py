from scenarios.loader import DEV_DIR, load_dir
from scenarios.schema import RootCause

SEEDS = load_dir(DEV_DIR)


def test_seed_scenarios_validate() -> None:
    by_difficulty = {s.difficulty: s.ground_truth.root_cause for s in SEEDS}

    assert len(SEEDS) == 3
    assert by_difficulty == {
        1: RootCause.CONFIG_ERROR,
        2: RootCause.DEPENDENCY_SLOWDOWN,
        3: RootCause.CERT_EXPIRY,
    }
