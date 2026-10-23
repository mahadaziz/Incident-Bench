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


def _keys_and_strings(node: Any) -> tuple[set[str], list[str]]:
    keys: set[str] = set()
    strings: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            keys.add(key)
            strings.append(key)
            sub_keys, sub_strings = _keys_and_strings(value)
            keys |= sub_keys
            strings += sub_strings
    elif isinstance(node, list):
        for item in node:
            sub_keys, sub_strings = _keys_and_strings(item)
            keys |= sub_keys
            strings += sub_strings
    elif isinstance(node, str):
        strings.append(node)
    return keys, strings


# Walks raw values, not JSON text: JSON escapes quotes, so a quoted secret would never match.
def _assert_no_leak(scenario: Scenario, also_hidden: Iterable[str] = ()) -> None:
    keys, strings = _keys_and_strings(scenario.agent_view().model_dump(mode="json"))
    gt = scenario.ground_truth

    assert not keys & set(HIDDEN_KEYS), f"agent view has hidden keys {keys & set(HIDDEN_KEYS)}"
    hidden = [
        scenario.id,
        scenario.title,
        gt.summary,
        *gt.acceptable_remediations,
        gt.root_cause.value,
        *also_hidden,
    ]
    for secret in hidden:
        assert not any(secret in text for text in strings), f"agent view leaks {secret!r}"


def test_agent_view_leaks_nothing_hidden(scenario_data: dict[str, Any]) -> None:
    scenario = Scenario.model_validate_json(json.dumps(scenario_data))

    _assert_no_leak(scenario, also_hidden=scenario.tags)


# Tags that are plain words legitimately found in evidence text; every other tag is checked.
EVIDENCE_WORD_TAGS = {"tls", "iam"}


@pytest.mark.parametrize("path", scenario_files(DEV_DIR), ids=lambda p: p.stem)
def test_seed_agent_view_leaks_nothing_hidden(path: Path) -> None:
    scenario = load_file(path)

    _assert_no_leak(scenario, also_hidden=set(scenario.tags) - EVIDENCE_WORD_TAGS)


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


def test_leak_check_catches_quoted_secrets(scenario_data: dict[str, Any]) -> None:
    scenario_data["title"] = 'cleanup "PR #812" broke it'
    scenario_data["logs"][0]["message"] = 'note: cleanup "PR #812" broke it'
    scenario = Scenario.model_validate_json(json.dumps(scenario_data))

    with pytest.raises(AssertionError, match="agent view leaks"):
        _assert_no_leak(scenario)
