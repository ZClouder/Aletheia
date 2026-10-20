from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from aletheia.cli import close_existing_loop
from aletheia.diagnosis import LLMAttributor, component_health, rule_diagnose
from aletheia.evaluators import JudgeOutput
from aletheia.models import (
    Diagnosis,
    DimensionScore,
    EvaluationResult,
    EvaluationRun,
    EvaluationSummary,
    RunManifest,
    Severity,
)
from aletheia.optimization import acceptance_gates, build_tasks
from aletheia.reporting import write_run
from aletheia.sample_app import sample_traces


def result(
    evaluator: str,
    score: float,
    dimension: str,
    trace_id: str = "trace-001",
) -> EvaluationResult:
    return EvaluationResult(
        trace_id=trace_id,
        case_id="case-001",
        evaluator=evaluator,
        score=score,
        reason="low score",
        dimensions=[DimensionScore(name=dimension, score=score)],
    )


def test_rule_diagnosis_maps_weakest_dimension_severity_and_stable_order() -> None:
    diagnoses = rule_diagnose(
        [
            result("rag", 0.6, "context_precision", "trace-002"),
            result("prompt", 0.2, "role", "trace-001"),
            result("agent", 0.9, "tool_success", "trace-003"),
        ]
    )
    assert [(item.component, item.severity) for item in diagnoses] == [
        ("Prompt", Severity.HIGH),
        ("RAG", Severity.MEDIUM),
    ]
    assert diagnoses[0].root_cause == "Prompt 缺少明确角色"
    assert diagnoses[1].root_cause == "检索上下文噪声过多"


@pytest.mark.asyncio
async def test_llm_attributor_repairs_json_and_returns_structured_diagnosis() -> None:
    outputs: Iterator[JudgeOutput] = iter(
        [
            JudgeOutput("broken", {}),
            JudgeOutput(
                '{"items":[{"trace_id":"trace-001","component":"Prompt",'
                '"severity":"high","root_cause":"缺少角色",'
                '"reason":"结构不完整","evidence":["role=0"]}]}',
                {},
            ),
        ]
    )

    async def judge(prompt: str) -> JudgeOutput:
        return next(outputs)

    low = result("prompt", 0.2, "role")
    rules = rule_diagnose([low])
    diagnoses = await LLMAttributor(judge).attribute(sample_traces()[:1], [low], rules)
    assert len(diagnoses) == 1
    assert diagnoses[0].source == "llm"
    assert diagnoses[0].severity is Severity.HIGH


@pytest.mark.asyncio
async def test_llm_attributor_skips_judge_when_no_rule_diagnosis() -> None:
    calls = 0

    async def judge(_: str) -> JudgeOutput:
        nonlocal calls
        calls += 1
        return JudgeOutput(text='{"items": []}', top_logprobs={})

    diagnoses = await LLMAttributor(judge).attribute([], [], [])

    assert diagnoses == []
    assert calls == 0


def test_component_health_contains_averages_overall_and_count() -> None:
    results = [result("prompt", 0.2, "role"), result("rag", 0.6, "context_precision")]
    diagnoses = rule_diagnose(results)
    health = component_health(results, diagnoses)
    assert health["Prompt"] == 0.2
    assert health["RAG"] == 0.6
    assert health["overall"] == pytest.approx(0.4)


def test_rule_diagnosis_can_emit_low_severity_with_higher_threshold() -> None:
    diagnoses = rule_diagnose([result("prompt", 0.75, "format")], threshold=0.8)
    assert diagnoses[0].severity is Severity.LOW


def test_tasks_group_same_root_cause_keep_highest_priority_and_deduplicate_evidence() -> None:
    diagnoses = [
        Diagnosis(
            trace_id="t1",
            component="RAG",
            severity=Severity.MEDIUM,
            reason="low",
            root_cause="噪声",
            evidence=["context_precision"],
        ),
        Diagnosis(
            trace_id="t2",
            component="RAG",
            severity=Severity.HIGH,
            reason="lower",
            root_cause="噪声",
            evidence=["context_precision"],
        ),
    ]
    tasks = build_tasks(diagnoses)
    assert len(tasks) == 1
    assert tasks[0].priority is Severity.HIGH
    assert tasks[0].evidence.count("context_precision") == 1
    assert "no regression" in tasks[0].acceptance_metric


def test_acceptance_gates_require_no_regression_and_one_improvement() -> None:
    passed = acceptance_gates({"rag": 0.5, "agent": 0.5}, {"rag": 0.8, "agent": 0.5})
    failed = acceptance_gates({"rag": 0.5, "agent": 0.5}, {"rag": 0.8, "agent": 0.4})
    assert all(passed.values())
    assert failed["no_regression:agent"] is False


def test_close_existing_loop_validates_lineage_and_writes_gates(tmp_path) -> None:
    def make_run(identifier: str, score: float) -> None:
        summary = EvaluationSummary(
            total_cases=1,
            successful_results=1,
            failed_results=0,
            pass_rate=float(score >= 0.7),
            evaluator_means={"rag": score},
        )
        manifest = RunManifest(
            run_id=identifier,
            stage=3,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            model="qwen",
            evaluation_set_sha256="a" * 64,
            trace_count=1,
            evaluators=["rag"],
            successful_results=1,
        )
        write_run(
            tmp_path,
            EvaluationRun(manifest=manifest, summary=summary, results=[]),
            sample_traces()[:1],
        )

    make_run("before", 0.5)
    make_run("after", 1.0)
    diagnosis = tmp_path / "diagnosis"
    diagnosis.mkdir()
    (diagnosis / "source-run.txt").write_text("before\n")
    optimization = tmp_path / "optimization"
    optimization.mkdir()
    (optimization / "source-diagnosis.txt").write_text("diagnosis\n")
    directory, payload = close_existing_loop(
        tmp_path, "before", "after", "diagnosis", "optimization"
    )
    assert payload["accepted"] is True
    assert (directory / "loop.json").is_file()
