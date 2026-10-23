from collections.abc import Iterable
from typing import Any

import pytest

from scenarios.loader import DEV_DIR, load_dir
from scenarios.schema import AgentView, Scenario


def test_agent_view_fields_are_exactly_the_allowlist() -> None:
    assert set(AgentView.model_fields) == {
        "alert",
        "logs",
        "metrics",
        "deploys",
        "configs",
        "budget",
    }


HIDDEN_KEYS = ["ground_truth", "required_evidence", "distractors", "difficulty", "source", "tags"]


def _assert_no_leak(scenario: Scenario, also_hidden: Iterable[str] = ()) -> None:
    dumped = scenario.agent_view().model_dump_json()
    gt = scenario.ground_truth

    hidden = [
        scenario.id,
        scenario.title,
        gt.summary,
        *gt.acceptable_remediations,
        gt.root_cause.value,
        *(f'"{key}"' for key in HIDDEN_KEYS),
        *also_hidden,
    ]
    for secret in hidden:
        assert secret not in dumped, f"agent view leaks {secret!r}"


def test_agent_view_leaks_nothing_hidden(scenario_data: dict[str, Any]) -> None:
    scenario = Scenario.model_validate(scenario_data)

    _assert_no_leak(scenario, also_hidden=scenario.tags)


# Seed tags are plain words ("tls", "iam") that legitimately appear in evidence text.
@pytest.mark.parametrize("scenario", load_dir(DEV_DIR), ids=lambda s: s.id)
def test_seed_agent_view_leaks_nothing_hidden(scenario: Scenario) -> None:
    _assert_no_leak(scenario)


def test_agent_view_shares_no_mutable_state(scenario_data: dict[str, Any]) -> None:
    scenario = Scenario.model_validate(scenario_data)

    scenario.agent_view().configs[0].values["INVENTORY_URL"] = "tampered"

    assert scenario.configs[0].values["INVENTORY_URL"] == "http://inventory:9000"


def test_agent_view_passes_evidence_through_unchanged(scenario_data: dict[str, Any]) -> None:
    scenario = Scenario.model_validate(scenario_data)

    view = scenario.agent_view()

    assert view.alert == scenario.alert
    assert view.logs == scenario.logs
    assert view.metrics == scenario.metrics
    assert view.deploys == scenario.deploys
    assert view.configs == scenario.configs
    assert view.budget == scenario.budget
