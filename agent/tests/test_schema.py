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


def _set_at(data: Any, path: tuple[Any, ...], value: Any) -> None:
    for key in path[:-1]:
        data = data[key]
    data[path[-1]] = value


# Matching message text is unreliable: pydantic echoes a truncated copy of the input.
def _reject_field(data: dict[str, Any], loc: tuple[Any, ...], error_type: str) -> None:
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate_json(json.dumps(data))
    errors = [(e["loc"], e["type"]) for e in exc.value.errors()]
    assert (loc, error_type) in errors, errors


def test_rejects_duplicate_id_within_kind(scenario_data: dict[str, Any]) -> None:
    scenario_data["logs"][1]["id"] = "log-001"
    _reject(scenario_data, r"duplicate evidence ids \['log-001'\]")


def test_rejects_unknown_required_evidence(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"][0].append("log-999")
    _reject(scenario_data, r"required_evidence references unknown ids \['log-999'\]")


def test_rejects_unknown_distractor(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["distractors"].append("dep-404")
    _reject(scenario_data, r"distractors references unknown ids \['dep-404'\]")


def test_rejects_id_both_required_and_distractor(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["distractors"].append("log-002")
    _reject(scenario_data, r"both required evidence and distractors \['log-002'\]")


def test_rejects_repeated_required_id(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"].append(["log-002"])
    _reject(scenario_data, r"required_evidence repeats \['log-002'\]")


def test_rejects_empty_required_evidence(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"] = []
    _reject_field(scenario_data, ("ground_truth", "required_evidence"), "too_short")


def test_rejects_empty_evidence_group(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"].append([])
    _reject_field(scenario_data, ("ground_truth", "required_evidence", 2), "too_short")


def test_accepts_alternative_ids_within_a_group(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"] = [["log-002", "met-001"], ["cfg-001"]]

    scenario = Scenario.model_validate_json(json.dumps(scenario_data))

    assert scenario.ground_truth.required_ids() == ("log-002", "met-001", "cfg-001")


def test_rejects_id_repeated_within_a_group(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"][0].append("log-002")
    _reject(scenario_data, r"required_evidence repeats \['log-002'\]")


@pytest.mark.parametrize(("value", "error_type"), [([], "too_short"), (None, "missing")])
def test_rejects_missing_distractors(
    scenario_data: dict[str, Any], value: Any, error_type: str
) -> None:
    if value is None:
        del scenario_data["ground_truth"]["distractors"]
    else:
        scenario_data["ground_truth"]["distractors"] = value
    _reject_field(scenario_data, ("ground_truth", "distractors"), error_type)


def test_rejects_unknown_affected_service(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["affected_service"] = "orders-apl"
    _reject(scenario_data, "affected_service 'orders-apl' is not a service")


@pytest.mark.parametrize(
    "path",
    [
        ("title",),
        ("alert", "summary"),
        ("logs", 0, "message"),
        ("ground_truth", "summary"),
        ("ground_truth", "acceptable_remediations", 0),
    ],
)
@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_rejects_blank_text(
    scenario_data: dict[str, Any], path: tuple[Any, ...], blank: str
) -> None:
    _set_at(scenario_data, path, blank)
    _reject_field(scenario_data, path, "string_pattern_mismatch")


def test_error_names_the_scenario(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["required_evidence"].append(["log-999"])
    _reject(scenario_data, "scenario 'fixture-orders-outage'")


@pytest.mark.parametrize(
    ("kind", "bad_id"),
    [
        ("logs", "dep-001"),
        ("logs", "log-1"),
        ("logs", "log-cert-expired"),
        ("logs", "log-0001"),
        ("metrics", "met-01"),
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
    _reject_field(scenario_data, (kind, 0, "id"), "string_pattern_mismatch")


@pytest.mark.parametrize("bad_id", ["the-bad-deploy", "log-0002", "log-١٢٣"])
def test_rejects_malformed_ground_truth_id(scenario_data: dict[str, Any], bad_id: str) -> None:
    scenario_data["ground_truth"]["required_evidence"] = [[bad_id]]
    _reject_field(
        scenario_data, ("ground_truth", "required_evidence", 0, 0), "string_pattern_mismatch"
    )


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
    _set_at(scenario_data, (*path, "distractor"), ["dep-001"])
    _reject_field(scenario_data, (*path, "distractor"), "extra_forbidden")


@pytest.mark.parametrize(
    ("difficulty", "error_type"), [(0, "greater_than_equal"), (4, "less_than_equal")]
)
def test_rejects_out_of_range_difficulty(
    scenario_data: dict[str, Any], difficulty: int, error_type: str
) -> None:
    scenario_data["difficulty"] = difficulty
    _reject_field(scenario_data, ("difficulty",), error_type)


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
    _set_at(scenario_data, path, "2026-01-10T12:00:00")
    _reject_field(scenario_data, path, "timezone_aware")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_rejects_non_finite_metric_value(scenario_data: dict[str, Any], value: float) -> None:
    scenario_data["metrics"][0]["points"][0]["value"] = value
    _reject_field(scenario_data, ("metrics", 0, "points", 0, "value"), "finite_number")


@pytest.mark.parametrize(
    ("path", "wrong_type", "error_type"),
    [
        (("difficulty",), True, "int_type"),
        (("difficulty",), "2", "int_type"),
        (("difficulty",), 2.0, "int_type"),
        (("budget", "max_steps"), "10", "int_type"),
        (("metrics", 0, "points", 0, "value"), "3", "float_type"),
    ],
)
def test_rejects_wrong_json_type_instead_of_coercing(
    scenario_data: dict[str, Any], path: tuple[Any, ...], wrong_type: Any, error_type: str
) -> None:
    _set_at(scenario_data, path, wrong_type)
    _reject_field(scenario_data, path, error_type)


def test_accepts_integer_metric_values(scenario_data: dict[str, Any]) -> None:
    scenario_data["metrics"][0]["points"][0]["value"] = 3

    _ = Scenario.model_validate_json(json.dumps(scenario_data))


@pytest.mark.parametrize("second", ["2026-01-10T11:59:00Z", "2026-01-10T12:00:00Z"])
def test_rejects_unordered_metric_points(scenario_data: dict[str, Any], second: str) -> None:
    scenario_data["metrics"][0]["points"][1]["timestamp"] = second
    _reject(scenario_data, "point timestamps must strictly increase")


def test_rejects_unknown_root_cause(scenario_data: dict[str, Any]) -> None:
    scenario_data["ground_truth"]["root_cause"] = "cosmic_rays"
    _reject_field(scenario_data, ("ground_truth", "root_cause"), "enum")


def test_rejects_unknown_source(scenario_data: dict[str, Any]) -> None:
    scenario_data["source"] = "imagined"
    _reject_field(scenario_data, ("source",), "enum")


@pytest.mark.parametrize("bad_id", ["Has-Caps", "spaces here", "trailing-", ""])
def test_rejects_malformed_scenario_id(scenario_data: dict[str, Any], bad_id: str) -> None:
    scenario_data["id"] = bad_id
    _reject_field(scenario_data, ("id",), "string_pattern_mismatch")


@pytest.mark.parametrize("field", ["max_steps", "max_tokens"])
def test_rejects_non_positive_budget(scenario_data: dict[str, Any], field: str) -> None:
    scenario_data["budget"][field] = 0
    _reject_field(scenario_data, ("budget", field), "greater_than")


@pytest.mark.parametrize(
    "bad", ["Search-Service", "order-service ", " order-service", "order_service"]
)
@pytest.mark.parametrize(
    "path",
    [
        ("alert", "service"),
        ("logs", 0, "service"),
        ("metrics", 0, "service"),
        ("deploys", 0, "service"),
        ("configs", 0, "service"),
        ("ground_truth", "affected_service"),
    ],
)
def test_rejects_non_slug_service_name(
    scenario_data: dict[str, Any], path: tuple[Any, ...], bad: str
) -> None:
    _set_at(scenario_data, path, bad)
    _reject_field(scenario_data, path, "string_pattern_mismatch")


@pytest.mark.parametrize("good_id", ["log-000", "log-999", "log-1000", "log-12345"])
def test_accepts_canonical_evidence_ids(scenario_data: dict[str, Any], good_id: str) -> None:
    scenario_data["logs"][0]["id"] = good_id

    _ = Scenario.model_validate_json(json.dumps(scenario_data))
