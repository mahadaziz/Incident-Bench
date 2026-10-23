from typing import Any

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


def test_agent_view_leaks_nothing_hidden(scenario_data: dict[str, Any]) -> None:
    scenario = Scenario.model_validate(scenario_data)

    dumped = scenario.agent_view().model_dump_json()

    hidden = [
        scenario.id,
        scenario.title,
        *scenario.tags,
        scenario.ground_truth.summary,
        *scenario.ground_truth.acceptable_remediations,
        scenario.ground_truth.root_cause.value,
        "ground_truth",
        "required_evidence",
        "distractors",
        "difficulty",
        '"source"',
    ]
    for secret in hidden:
        assert secret not in dumped, f"agent view leaks {secret!r}"


def test_agent_view_passes_evidence_through_unchanged(scenario_data: dict[str, Any]) -> None:
    scenario = Scenario.model_validate(scenario_data)

    view = scenario.agent_view()

    assert view.alert == scenario.alert
    assert view.logs == scenario.logs
    assert view.metrics == scenario.metrics
    assert view.deploys == scenario.deploys
    assert view.configs == scenario.configs
    assert view.budget == scenario.budget
