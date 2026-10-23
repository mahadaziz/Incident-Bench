import json
from pathlib import Path
from typing import Any

import pytest

from scenarios.loader import ScenarioLoadError, load_dir, load_dirs


def _write(directory: Path, data: dict[str, Any], name: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    file = directory / f"{name or data['id']}.json"
    file.write_text(json.dumps(data), encoding="utf-8")
    return file


def test_loads_scenarios_sorted_by_id(tmp_path: Path, scenario_data: dict[str, Any]) -> None:
    for scenario_id in ["zeta", "alpha", "mid"]:
        _write(tmp_path, {**scenario_data, "id": scenario_id})

    assert [s.id for s in load_dir(tmp_path)] == ["alpha", "mid", "zeta"]


def test_ignores_hidden_files(tmp_path: Path, scenario_data: dict[str, Any]) -> None:
    _write(tmp_path, scenario_data)
    (tmp_path / ".gitkeep").touch()

    assert len(load_dir(tmp_path)) == 1


def test_rejects_filename_not_matching_id(tmp_path: Path, scenario_data: dict[str, Any]) -> None:
    _write(tmp_path, scenario_data, name="something-else")

    with pytest.raises(ScenarioLoadError, match="filename must match scenario id"):
        load_dir(tmp_path)


def test_rejects_duplicate_id_across_directories(
    tmp_path: Path, scenario_data: dict[str, Any]
) -> None:
    _write(tmp_path / "dev", scenario_data)
    _write(tmp_path / "test", scenario_data)

    with pytest.raises(ScenarioLoadError, match="also in"):
        load_dirs([tmp_path / "dev", tmp_path / "test"])


def test_rejects_malformed_json_naming_the_file(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ScenarioLoadError, match="broken.json"):
        load_dir(tmp_path)


def test_rejects_duplicate_json_keys(tmp_path: Path, scenario_data: dict[str, Any]) -> None:
    text = json.dumps(scenario_data).replace(
        '"distractors": ["dep-001"]', '"distractors": ["dep-001"], "distractors": []'
    )
    assert text.count('"distractors"') == 2
    (tmp_path / f"{scenario_data['id']}.json").write_text(text, encoding="utf-8")

    with pytest.raises(ScenarioLoadError, match=r"duplicate JSON keys \['distractors'\]"):
        load_dir(tmp_path)


def test_rejects_invalid_scenario_naming_the_file(
    tmp_path: Path, scenario_data: dict[str, Any]
) -> None:
    scenario_data["ground_truth"]["required_evidence"] = ["log-999"]
    _write(tmp_path, scenario_data)

    with pytest.raises(ScenarioLoadError, match=r"(?s)fixture-orders-outage\.json.*log-999"):
        load_dir(tmp_path)


def test_rejects_hidden_json_file(tmp_path: Path, scenario_data: dict[str, Any]) -> None:
    _write(tmp_path, scenario_data)
    _write(tmp_path, {**scenario_data, "id": "other"}, name=".other")

    with pytest.raises(ScenarioLoadError, match=r"\.other\.json"):
        load_dir(tmp_path)


@pytest.mark.parametrize("name", ["notes.txt", "scenario.yaml", "subdir"])
def test_rejects_non_scenario_entries(
    tmp_path: Path, scenario_data: dict[str, Any], name: str
) -> None:
    _write(tmp_path, scenario_data)
    if name == "subdir":
        (tmp_path / name).mkdir()
    else:
        (tmp_path / name).touch()

    with pytest.raises(ScenarioLoadError, match="not a .json scenario file"):
        load_dir(tmp_path)


def test_wraps_read_errors_naming_the_file(
    tmp_path: Path, scenario_data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, scenario_data)

    def _deny(self: Path) -> bytes:
        raise PermissionError("access denied")

    monkeypatch.setattr(Path, "read_bytes", _deny)

    with pytest.raises(ScenarioLoadError, match=r"(?s)fixture-orders-outage\.json.*access denied"):
        load_dir(tmp_path)


def test_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ScenarioLoadError, match="no scenarios found"):
        load_dir(tmp_path)


def test_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ScenarioLoadError, match="not a directory"):
        load_dir(tmp_path / "nope")
