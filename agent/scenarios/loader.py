import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from scenarios.schema import Scenario

DATA_DIR = Path(__file__).parent / "data"
DEV_DIR = DATA_DIR / "dev"


class ScenarioLoadError(Exception):
    pass


def load_dir(path: Path) -> list[Scenario]:
    return load_dirs([path])


def load_dirs(paths: Iterable[Path]) -> list[Scenario]:
    loaded: dict[str, tuple[Scenario, Path]] = {}
    for directory in paths:
        for file in scenario_files(directory):
            scenario = load_file(file)
            if scenario.id in loaded:
                other = loaded[scenario.id][1]
                raise ScenarioLoadError(f"{file}: scenario id {scenario.id!r} also in {other}")
            loaded[scenario.id] = (scenario, file)
    if not loaded:
        raise ScenarioLoadError("no scenario directories given")
    return [scenario for _, (scenario, _) in sorted(loaded.items())]


def scenario_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise ScenarioLoadError(f"{directory}: not a directory")
    # Reject rather than skip, so a misnamed scenario can't silently drop out of the set.
    files = []
    for entry in sorted(directory.iterdir()):
        if entry.name.startswith(".") and not entry.name.lower().endswith(".json"):
            continue
        if not entry.is_file() or entry.suffix != ".json":
            raise ScenarioLoadError(f"{entry}: not a .json scenario file")
        files.append(entry)
    if not files:
        raise ScenarioLoadError(f"{directory}: no scenarios found")
    return files


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    counts = Counter(key for key, _ in pairs)
    if dupes := sorted(key for key, n in counts.items() if n > 1):
        raise ValueError(f"duplicate JSON keys {dupes}")
    return dict(pairs)


def load_file(file: Path) -> Scenario:
    # Parsed twice on purpose: pydantic keeps the last of a repeated key, json.loads can reject it.
    try:
        try:
            text = file.read_bytes().decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"not UTF-8 ({e}); save as UTF-8 without BOM") from e
        if text.startswith("﻿"):
            raise ValueError("starts with a UTF-8 byte-order mark; save as UTF-8 without BOM")
        json.loads(text, object_pairs_hook=_reject_duplicate_keys)
        scenario = Scenario.model_validate_json(text)
    except (OSError, ValueError, ValidationError) as e:
        raise ScenarioLoadError(f"{file}: {e}") from e
    if file.stem != scenario.id:
        raise ScenarioLoadError(f"{file}: filename must match scenario id {scenario.id!r}")
    return scenario
