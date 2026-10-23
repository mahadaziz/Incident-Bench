import json
from typing import Any

import pytest
from pydantic import ValidationError

from scenarios.schema import RootCause, Scenario


def test_valid_scenario_loads(scenario_data: dict[str, Any]) -> None:
    scenario = Scenario.model_validate_json(json.dumps(scenario_data))

    assert scenario.ground_truth.root_cause is RootCause.CONFIG_ERROR
    assert scenario.evidence_ids() == {"log-001", "log-002", "met-001", "dep-001", "cfg-001"}


def test_scenario_is_immutable(scenario_data: dict[str, Any]) -> None:
    scenario = Scenario.model_validate_json(json.dumps(scenario_data))

    with pytest.raises(ValidationError):
        scenario.difficulty = 3  # type: ignore[misc]


def _reject(data: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        Scenario.model_validate_json(json.dumps(data))


def test_rejects_duplicate_id_within_kind(scenario_data: dict[str, Any]) -> None:
    scenario_data["logs"][1]["id"] = "log-001"
    _reject(scenario_data, r"duplicate evidence ids \['log-001'\]")


def test_rejects_unknown_required_evidence(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"].append("log-999")
    _reject(scenario_data, r"required_evidence references unknown ids \['log-999'\]")


def test_rejects_unknown_distractor(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["distractors"].append("dep-404")
    _reject(scenario_data, r"distractors references unknown ids \['dep-404'\]")


def test_rejects_id_both_required_and_distractor(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["distractors"].append("log-002")
    _reject(scenario_data, r"both required evidence and distractors \['log-002'\]")


def test_rejects_repeated_required_id(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"].append("log-002")
    _reject(scenario_data, r"required_evidence repeats \['log-002'\]")


def test_rejects_empty_required_evidence(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"] = []
    _reject(scenario_data, "required_evidence")


@pytest.mark.parametrize("value", [[], None])
def test_rejects_missing_distractors(scenario_data: dict[str, Any], value: Any) -> None:
    if value is None:
        del scenario_data["ground_truth"]["distractors"]
    else:
        scenario_data["ground_truth"]["distractors"] = value
    _reject(scenario_data, "distractors")


def test_error_names_the_scenario(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"].append("log-999")
    _reject(scenario_data, "scenario 'fixture-orders-outage'")


@pytest.mark.parametrize(
    ("kind", "bad_id"),
    [
        ("logs", "dep-001"),
        ("logs", "log-1"),
        ("logs", "log-cert-expired"),
        ("logs", "log-١٢٣"),
        ("metrics", "log-005"),
        ("deploys", "dep-latest"),
        ("configs", "config-001"),
    ],
)
def test_rejects_malformed_evidence_id(
    scenario_data: dict[str, Any], kind: str, bad_id: str
) -> None:
    scenario_data[kind][0]["id"] = bad_id
    _reject(scenario_data, "String should match pattern")


@pytest.mark.parametrize("bad_id", ["the-bad-deploy", "log-١٢٣"])
def test_rejects_malformed_ground_truth_id(scenario_data: dict[str, Any], bad_id: str) -> None:
    scenario_data["ground_truth"]["required_evidence"] = [bad_id]
    _reject(scenario_data, "String should match pattern")


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("alert",),
        ("logs", 0),
        ("ground_truth",),
        ("budget",),
    ],
)
def test_rejects_unknown_field(scenario_data: dict[str, Any], path: tuple[Any, ...]) -> None:
    target: Any = scenario_data
    for key in path:
        target = target[key]
    target["distractor"] = ["dep-001"]
    _reject(scenario_data, "Extra inputs are not permitted")


@pytest.mark.parametrize("difficulty", [0, 4])
def test_rejects_out_of_range_difficulty(scenario_data: dict[str, Any], difficulty: int) -> None:
    scenario_data["difficulty"] = difficulty
    _reject(scenario_data, "difficulty")


@pytest.mark.parametrize(
    "path",
    [
        ("alert", "fired_at"),
        ("logs", 0, "timestamp"),
        ("metrics", 0, "points", 0, "timestamp"),
        ("deploys", 0, "timestamp"),
        ("configs", 0, "captured_at"),
    ],
)
def test_rejects_naive_timestamp(scenario_data: dict[str, Any], path: tuple[Any, ...]) -> None:
    target: Any = scenario_data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = "2026-01-10T12:00:00"
    _reject(scenario_data, "timezone")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_rejects_non_finite_metric_value(scenario_data: dict[str, Any], value: float) -> None:
    scenario_data["metrics"][0]["points"][0]["value"] = value
    _reject(scenario_data, "finite number")


@pytest.mark.parametrize(
    ("path", "wrong_type"),
    [
        (("difficulty",), True),
        (("difficulty",), "2"),
        (("budget", "max_steps"), "10"),
        (("metrics", 0, "points", 0, "value"), "3"),
        (("configs", 0, "values", "INVENTORY_URL"), 9000),
    ],
)
def test_rejects_wrong_json_type_instead_of_coercing(
    scenario_data: dict[str, Any], path: tuple[Any, ...], wrong_type: Any
) -> None:
    target: Any = scenario_data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = wrong_type
    _reject(scenario_data, "valid")


def test_accepts_integer_metric_values(scenario_data: dict[str, Any]) -> None:
    scenario_data["metrics"][0]["points"][0]["value"] = 3

    _ = Scenario.model_validate_json(json.dumps(scenario_data))


def test_rejects_unknown_root_cause(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["root_cause"] = "cosmic_rays"
    _reject(scenario_data, "root_cause")


def test_rejects_unknown_source(scenario_data: dict[str, Any]) -> None:
    scenario_data["source"] = "imagined"
    _reject(scenario_data, "source")


@pytest.mark.parametrize("bad_id", ["Has-Caps", "spaces here", "trailing-", ""])
def test_rejects_malformed_scenario_id(scenario_data: dict[str, Any], bad_id: str) -> None:
    scenario_data["id"] = bad_id
    _reject(scenario_data, "id")


@pytest.mark.parametrize("field", ["max_steps", "max_tokens"])
def test_rejects_non_positive_budget(scenario_data: dict[str, Any], field: str) -> None:
    scenario_data["budget"][field] = 0
    _reject(scenario_data, field)
