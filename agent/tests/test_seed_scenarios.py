from scenarios.loader import DEV_DIR, load_dir
from scenarios.schema import RootCause, Source

SEED_IDS = {
    "seed-renamed-env-var": (1, RootCause.CONFIG_ERROR),
    "seed-payments-pool-exhaustion": (2, RootCause.DEPENDENCY_SLOWDOWN),
    "seed-cert-expiry-iam": (3, RootCause.CERT_EXPIRY),
}


def test_seed_scenarios_validate() -> None:
    dev = {s.id: s for s in load_dir(DEV_DIR)}

    assert SEED_IDS.keys() <= dev.keys()
    for seed_id, expected in SEED_IDS.items():
        seed = dev[seed_id]
        assert (seed.difficulty, seed.ground_truth.root_cause) == expected
        assert seed.source is Source.SYNTHETIC
