from collections import Counter
from collections.abc import Iterator
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(StrEnum):
    REAL = "real"
    SYNTHETIC = "synthetic"


class RootCause(StrEnum):
    BAD_DEPLOY = "bad_deploy"
    CONFIG_ERROR = "config_error"
    DEPENDENCY_SLOWDOWN = "dependency_slowdown"
    CERT_EXPIRY = "cert_expiry"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    TRAFFIC_SPIKE = "traffic_spike"
    DATA_ISSUE = "data_issue"
    INFRA_FAILURE = "infra_failure"


Text = Annotated[str, StringConstraints(min_length=1)]
ScenarioId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
# Evidence ids must stay opaque (kind + number): a descriptive id would leak the answer.
LogId = Annotated[str, StringConstraints(pattern=r"^log-\d{3,}$")]
MetricId = Annotated[str, StringConstraints(pattern=r"^met-\d{3,}$")]
DeployId = Annotated[str, StringConstraints(pattern=r"^dep-\d{3,}$")]
ConfigId = Annotated[str, StringConstraints(pattern=r"^cfg-\d{3,}$")]
EvidenceId = Annotated[str, StringConstraints(pattern=r"^(log|met|dep|cfg)-\d{3,}$")]


class Alert(_Model):
    name: Text
    service: Text
    severity: Literal["critical", "warning", "info"]
    fired_at: AwareDatetime
    summary: Text


class LogLine(_Model):
    id: LogId
    timestamp: AwareDatetime
    service: Text
    level: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
    message: Text


class MetricPoint(_Model):
    timestamp: AwareDatetime
    value: float


class MetricSeries(_Model):
    id: MetricId
    name: Text
    service: Text
    unit: Text
    points: tuple[MetricPoint, ...] = Field(min_length=1)


class Deploy(_Model):
    id: DeployId
    service: Text
    version: Text
    timestamp: AwareDatetime
    author: Text
    description: Text


class ConfigSnapshot(_Model):
    id: ConfigId
    service: Text
    captured_at: AwareDatetime
    values: dict[str, str] = Field(min_length=1)


class GroundTruth(_Model):
    root_cause: RootCause
    summary: Text
    affected_service: Text
    required_evidence: tuple[EvidenceId, ...] = Field(min_length=1)
    distractors: tuple[EvidenceId, ...] = ()
    acceptable_remediations: tuple[Text, ...] = Field(min_length=1)


class Budget(_Model):
    max_steps: int = Field(gt=0)
    max_tokens: int = Field(gt=0)


class Scenario(_Model):
    id: ScenarioId
    title: Text
    source: Source
    difficulty: int = Field(ge=1, le=3)
    tags: tuple[Text, ...] = ()
    alert: Alert
    logs: tuple[LogLine, ...] = ()
    metrics: tuple[MetricSeries, ...] = ()
    deploys: tuple[Deploy, ...] = ()
    configs: tuple[ConfigSnapshot, ...] = ()
    ground_truth: GroundTruth
    budget: Budget

    def _evidence(self) -> Iterator[LogLine | MetricSeries | Deploy | ConfigSnapshot]:
        yield from self.logs
        yield from self.metrics
        yield from self.deploys
        yield from self.configs

    def evidence_ids(self) -> frozenset[str]:
        return frozenset(item.id for item in self._evidence())

    @model_validator(mode="after")
    def _check_evidence_ids(self) -> Self:
        gt = self.ground_truth
        problems = []

        id_counts = Counter(item.id for item in self._evidence())
        if dupes := sorted(i for i, n in id_counts.items() if n > 1):
            problems.append(f"duplicate evidence ids {dupes}")

        for field in ("required_evidence", "distractors"):
            ids = getattr(gt, field)
            if dupes := sorted(i for i, n in Counter(ids).items() if n > 1):
                problems.append(f"ground_truth.{field} repeats {dupes}")
            if unknown := sorted(set(ids) - id_counts.keys()):
                problems.append(f"ground_truth.{field} references unknown ids {unknown}")

        if overlap := sorted(set(gt.required_evidence) & set(gt.distractors)):
            problems.append(f"ids are both required evidence and distractors {overlap}")

        if problems:
            raise ValueError(f"scenario {self.id!r}: " + "; ".join(problems))
        return self
