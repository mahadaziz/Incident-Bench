import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

from scenarios.loader import DEV_DIR, load_file, scenario_files
from scenarios.schema import AgentView, Scenario


def test_agent_view_fields_are_exactly_the_allowlist() -> None:
    assert set(AgentView.model_fields) == {
        "alert",
        "logs",
        "metrics",
        "deploys",
        "configs",
    }


HIDDEN_KEYS = [
    "ground_truth",
    "required_evidence",
    "distractors",
    "difficulty",
    "source",
    "tags",
    "max_steps",
    "max_tokens",
]


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
    scenario = Scenario.model_validate_json(json.dumps(scenario_data))

    _assert_no_leak(scenario, also_hidden=scenario.tags)


# Seed tags are plain words ("tls", "iam") that legitimately appear in evidence text.
@pytest.mark.parametrize("path", scenario_files(DEV_DIR), ids=lambda p: p.stem)
def test_seed_agent_view_leaks_nothing_hidden(path: Path) -> None:
    _assert_no_leak(load_file(path))


def test_agent_view_shares_no_mutable_state(scenario_data: dict[str, Any]) -> None:
    scenario = Scenario.model_validate_json(json.dumps(scenario_data))

    scenario.agent_view().configs[0].values["INVENTORY_URL"] = "tampered"

    assert scenario.configs[0].values["INVENTORY_URL"] == "http://inventory:9000"


def test_agent_view_passes_evidence_through_unchanged(scenario_data: dict[str, Any]) -> None:
    scenario = Scenario.model_validate_json(json.dumps(scenario_data))

    view = scenario.agent_view()

    assert view.alert == scenario.alert
    assert view.logs == scenario.logs
    assert view.metrics == scenario.metrics
    assert view.deploys == scenario.deploys
    assert view.configs == scenario.configs
