from __future__ import annotations

import pytest

from aletheia.cli import build_parser, stage_cases
from aletheia.engine import compare_summaries, summarize
from aletheia.evaluators import AgentEvaluator, RAGEvaluator, SkillEvaluator
from aletheia.models import EvaluationCase, EvaluationResult
from aletheia.sample_app import REFERENCE, sample_traces


def case(trace_id: str) -> EvaluationCase:
    return EvaluationCase(
        id=f"case-{trace_id}",
        trace_id=trace_id,
        reference_answer=REFERENCE,
        evaluators=["prompt", "g-eval"],
        expected={
            "relevant_document_ids": ["parenting-1"],
            "skill": "parenting",
            "tools": ["task_splitter"],
            "tool_args": {"task_splitter": {"minutes": 20, "parts": 4}},
        },
    )


@pytest.mark.asyncio
async def test_rag_evaluator_reports_five_dimensions_and_optimized_improves_precision() -> None:
    baseline = sample_traces("baseline")[0]
    optimized = sample_traces("optimized")[0]
    evaluator = RAGEvaluator()
    left = await evaluator.evaluate(baseline, case(baseline.id))
    right = await evaluator.evaluate(optimized, case(optimized.id))
    assert [item.name for item in left.dimensions] == [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "citation_correctness",
    ]
    assert right.score > left.score
    assert right.dimensions[2].score == 1


@pytest.mark.asyncio
async def test_rag_evaluator_handles_missing_retrieval() -> None:
    trace = sample_traces("baseline")[0].model_copy(
        update={"spans": [span for span in sample_traces()[0].spans if span.kind != "retrieval"]}
    )
    result = await RAGEvaluator().evaluate(trace, case(trace.id))
    assert result.score == 0
    assert "缺少" in result.reason


@pytest.mark.asyncio
async def test_skill_evaluator_detects_wrong_selection_and_optimized_repairs_it() -> None:
    baseline = sample_traces("baseline")[1]
    optimized = sample_traces("optimized")[1]
    left = await SkillEvaluator().evaluate(baseline, case(baseline.id))
    right = await SkillEvaluator().evaluate(optimized, case(optimized.id))
    assert left.score == 0
    assert right.score == 1


@pytest.mark.asyncio
async def test_agent_evaluator_detects_args_error_repeat_and_completion() -> None:
    evaluator = AgentEvaluator()
    traces = sample_traces("baseline")
    wrong_args = await evaluator.evaluate(traces[2], case(traces[2].id))
    failed = await evaluator.evaluate(traces[3], case(traces[3].id))
    repeated = await evaluator.evaluate(traces[4], case(traces[4].id))
    assert wrong_args.dimensions[1].score == 0
    assert failed.dimensions[2].score == 0
    assert repeated.dimensions[3].score == 0
    optimized = sample_traces("optimized")[4]
    repaired = await evaluator.evaluate(optimized, case(optimized.id))
    assert repaired.score == 1


def test_stage2_routes_all_evaluators_without_mutating_stage1_cases() -> None:
    original = case("trace-001")
    selected = stage_cases([original], 2)[0]
    assert original.evaluators == ["prompt", "g-eval"]
    assert selected.evaluators == ["prompt", "g-eval", "rag", "skill", "agent"]


def test_comparison_reports_evaluator_dimension_and_pass_rate_deltas() -> None:
    before_result = EvaluationResult(
        trace_id="t",
        case_id="c",
        evaluator="rag",
        score=0.5,
        reason="before",
    )
    after_result = before_result.model_copy(update={"score": 1.0, "reason": "after"})
    before = summarize([before_result], 1, 0.7)
    after = summarize([after_result], 1, 0.7)
    delta = compare_summaries(before, after)
    assert delta["evaluators"]["rag"] == pytest.approx(0.5)
    assert delta["overall"]["pass_rate"] == 1


def test_compare_cli_supports_config_and_model_modes() -> None:
    parser = build_parser()
    default = parser.parse_args(["compare"])
    models = parser.parse_args(
        [
            "compare",
            "--mode",
            "model",
            "--before-model",
            "small",
            "--after-model",
            "large",
        ]
    )
    assert default.mode == "config"
    assert (models.mode, models.before_model, models.after_model) == (
        "model",
        "small",
        "large",
    )
