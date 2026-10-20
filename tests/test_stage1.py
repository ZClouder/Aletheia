from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aletheia.config import AppConfig
from aletheia.engine import EvaluationEngine, summarize
from aletheia.evaluators import (
    EvaluatorRegistry,
    GEvalEvaluator,
    JudgeOutput,
    PromptEvaluator,
    extract_json,
    normalized_logprob_score,
)
from aletheia.models import (
    EvaluationCase,
    EvaluationResult,
    EvaluationRun,
    RunManifest,
    Span,
    SpanKind,
    Trace,
)
from aletheia.observability import TraceEvent
from aletheia.reporting import write_run
from aletheia.sample_app import sample_traces
from aletheia.storage import JsonlTraceStore, load_cases


def evaluation_case(trace_id: str = "trace-001") -> EvaluationCase:
    return EvaluationCase(
        id="case-1",
        trace_id=trace_id,
        reference_answer="先共情，再拆分任务，建立节奏。",
        evaluators=["prompt"],
    )


def test_trace_contract_rejects_unknown_kind_duplicate_span_and_negative_duration() -> None:
    with pytest.raises(ValidationError):
        Span(id="s", name="x", kind="unknown", duration_ms=1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Span(id="s", name="x", kind=SpanKind.PROMPT, duration_ms=-1)
    span = Span(id="s", name="x", kind=SpanKind.PROMPT, duration_ms=1)
    with pytest.raises(ValidationError, match="unique"):
        Trace(id="t", query="q", response="a", spans=[span, span], model="m")


def test_config_is_strict_and_validates_threshold(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """llm: {base_url: http://localhost, model: qwen}
judge: {model: qwen}
data: {traces: data/t.jsonl, evaluation_set: data/e.json}
output: {directory: output}
thresholds: {pass_score: 1.1}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        AppConfig.from_yaml(path)


def test_trace_store_round_trip_duplicate_and_bad_line(tmp_path: Path) -> None:
    store = JsonlTraceStore(tmp_path / "traces.jsonl")
    traces = sample_traces()[:2]
    store.replace(traces)
    assert store.read_all() == traces
    with pytest.raises(ValueError, match="duplicate"):
        store.append(traces[0])
    store.path.write_text('{"bad":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        store.read_all()


def test_case_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    raw = evaluation_case().model_dump(mode="json")
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([raw, raw]), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_cases(path)


@pytest.mark.asyncio
async def test_prompt_evaluator_scores_four_dimensions_and_missing_span() -> None:
    complete, missing_span = sample_traces()[0], sample_traces()[-1]
    evaluator = PromptEvaluator()
    result = await evaluator.evaluate(complete, evaluation_case(complete.id))
    assert result.score == 1
    assert [item.name for item in result.dimensions] == [
        "role",
        "task",
        "constraint",
        "format",
    ]
    missing = await evaluator.evaluate(missing_span, evaluation_case(missing_span.id))
    assert missing.score == 0
    assert len(missing.dimensions) == 4


def test_json_extraction_and_logprob_expected_score() -> None:
    assert extract_json('text ```json {"reason":"ok"} ```')["reason"] == "ok"
    score = normalized_logprob_score({" 5": -0.1, "4": -2.0, "other": -0.01})
    assert 0.9 < score <= 1
    with pytest.raises(ValueError, match="no score token"):
        normalized_logprob_score({"x": -0.1})


@pytest.mark.asyncio
async def test_geval_repairs_analysis_and_uses_logprob_probability() -> None:
    outputs = iter(
        [
            JudgeOutput("broken", {}),
            JudgeOutput('{"reason":"完整","evidence":["三项建议"]}', {}),
            JudgeOutput("5", {"5": -0.1, "4": -3.0}),
        ]
    )

    async def judge(prompt: str) -> JudgeOutput:
        return next(outputs)

    trace = sample_traces()[0]
    result = await GEvalEvaluator(judge).evaluate(trace, evaluation_case(trace.id))
    assert result.score > 0.95
    assert result.degraded is False
    assert result.evidence == ["三项建议"]


@pytest.mark.asyncio
async def test_geval_falls_back_to_score_token_without_logprobs() -> None:
    outputs = iter(
        [
            JudgeOutput('{"reason":"部分完整","evidence":[]}', {}),
            JudgeOutput("4", {}),
        ]
    )

    async def judge(prompt: str) -> JudgeOutput:
        return next(outputs)

    trace = sample_traces()[0]
    result = await GEvalEvaluator(judge).evaluate(trace, evaluation_case(trace.id))
    assert result.score == 0.75
    assert result.degraded is True


def test_registry_rejects_duplicates_and_unknown_name() -> None:
    with pytest.raises(ValueError, match="unique"):
        EvaluatorRegistry([PromptEvaluator(), PromptEvaluator()])
    registry = EvaluatorRegistry([PromptEvaluator()])
    assert registry.names == ["prompt"]
    with pytest.raises(ValueError, match="unknown"):
        registry.get("missing")


@pytest.mark.asyncio
async def test_engine_preserves_order_limits_concurrency_and_isolates_failure() -> None:
    events: list[TraceEvent] = []
    active = 0
    maximum = 0

    class TrackingEvaluator:
        name = "tracking"

        async def evaluate(self, trace: Trace, case: EvaluationCase) -> EvaluationResult:
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.01)
            active -= 1
            if case.id == "bad":
                raise RuntimeError("expected")
            return EvaluationResult(
                trace_id=trace.id,
                case_id=case.id,
                evaluator=self.name,
                score=1,
                reason="ok",
            )

    traces = sample_traces()[:3]
    cases = [
        EvaluationCase(
            id="bad" if index == 1 else f"c{index}",
            trace_id=trace.id,
            reference_answer="answer",
            evaluators=["tracking"],
        )
        for index, trace in enumerate(traces)
    ]
    results = await EvaluationEngine(
        EvaluatorRegistry([TrackingEvaluator()]),
        max_concurrency=2,
        trace_observer=events.append,
        run_id="test-run",
    ).run(traces, cases)
    assert [item.case_id for item in results] == ["c0", "bad", "c2"]
    assert maximum == 2
    assert results[1].error == "RuntimeError: expected"
    assert events[0].name == "evaluation.start"
    assert events[-1].name == "evaluation.finish"
    assert any(event.name == "evaluator.failed" for event in events)
    assert {event.run_id for event in events} == {"test-run"}


def test_summary_and_run_writer_create_machine_and_human_outputs(tmp_path: Path) -> None:
    result = EvaluationResult(
        trace_id="trace-001",
        case_id="case-1",
        evaluator="prompt",
        score=1,
        reason="ok",
    )
    summary = summarize([result], 1, 0.7)
    manifest = RunManifest(
        run_id="run-test",
        stage=1,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        model="qwen",
        evaluation_set_sha256="a" * 64,
        trace_count=1,
        evaluators=["prompt"],
        successful_results=1,
    )
    directory = write_run(
        tmp_path,
        EvaluationRun(manifest=manifest, summary=summary, results=[result]),
        sample_traces()[:1],
    )
    assert {path.name for path in directory.iterdir()} == {
        "manifest.json",
        "traces.jsonl",
        "evaluation-results.json",
        "evaluation-summary.json",
        "evaluation-report.md",
    }
    with pytest.raises(FileExistsError):
        write_run(
            tmp_path,
            EvaluationRun(manifest=manifest, summary=summary, results=[result]),
            sample_traces()[:1],
        )
