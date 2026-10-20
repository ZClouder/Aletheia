from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """所有输入契约的共同基类；extra=forbid 会拒绝拼错或未声明字段。"""

    model_config = ConfigDict(extra="forbid")


class SpanKind(StrEnum):
    """StrEnum 的成员既有枚举约束，也能像字符串一样写入 JSON。"""

    PROMPT = "prompt"
    RETRIEVAL = "retrieval"
    SKILL = "skill"
    TOOL = "tool"
    GENERATION = "generation"


class Span(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: SpanKind
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = Field(ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)


class Trace(StrictModel):
    """一次真实应用调用及其内部 Span；它是评测系统的最小输入单元。"""

    id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    response: str = Field(min_length=1)
    spans: list[Span] = Field(min_length=1)
    model: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_span_ids(self) -> Trace:
        # after 表示先完成字段类型校验，再检查“同一 Trace 内 ID 唯一”的跨字段规则。
        ids = [span.id for span in self.spans]
        if len(ids) != len(set(ids)):
            raise ValueError("span ids must be unique within a trace")
        return self


class EvaluationCase(StrictModel):
    id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    reference_answer: str = Field(min_length=1)
    evaluators: list[str] = Field(min_length=1)
    expected: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DimensionScore(StrictModel):
    name: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    reason: str = ""


class EvaluationResult(StrictModel):
    trace_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    evaluator: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    reason: str
    evidence: list[str] = Field(default_factory=list)
    dimensions: list[DimensionScore] = Field(default_factory=list)
    degraded: bool = False
    raw_judge: str | None = None
    error: str | None = None


class EvaluationSummary(StrictModel):
    total_cases: int = Field(ge=0)
    successful_results: int = Field(ge=0)
    failed_results: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    evaluator_means: dict[str, float] = Field(default_factory=dict)
    dimension_means: dict[str, float] = Field(default_factory=dict)


class RunManifest(StrictModel):
    run_id: str = Field(min_length=1)
    stage: int = Field(ge=1, le=3)
    started_at: datetime
    completed_at: datetime | None = None
    model: str = Field(min_length=1)
    evaluation_set_sha256: str = Field(min_length=64, max_length=64)
    trace_count: int = Field(ge=0)
    evaluators: list[str]
    successful_results: int = Field(default=0, ge=0)
    failed_results: int = Field(default=0, ge=0)
    config: dict[str, Any] = Field(default_factory=dict)


class EvaluationRun(StrictModel):
    manifest: RunManifest
    summary: EvaluationSummary
    results: list[EvaluationResult]


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Diagnosis(StrictModel):
    trace_id: str
    component: str
    severity: Severity
    reason: str
    root_cause: str = ""
    evidence: list[str] = Field(default_factory=list)
    source: str = "rule"


class OptimizationTask(StrictModel):
    title: str
    priority: Severity = Severity.MEDIUM
    component: str
    action: str
    evidence: list[str] = Field(default_factory=list)
    acceptance_metric: str
