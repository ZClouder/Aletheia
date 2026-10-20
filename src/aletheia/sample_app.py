from __future__ import annotations

from .models import Span, SpanKind, Trace

REFERENCE = "先共情孩子的困难，再拆分任务，并建立固定学习节奏。"


def _prompt(case: str) -> str:
    complete = (
        "你是一位专业育儿顾问。请基于资料回答问题，必须给出三个可执行建议，"
        "使用编号列表格式，禁止虚构。"
    )
    variants = {
        "complete": complete,
        "missing_role": "请基于资料回答问题，必须给出三个建议，使用列表格式。",
        "missing_task": "你是一位专业育儿顾问。必须基于资料，使用列表格式，禁止虚构。",
        "missing_constraint": "你是一位专业育儿顾问，请回答孩子作业拖延问题，使用列表格式。",
        "missing_format": "你是一位专业育儿顾问，请基于资料回答，必须给出可执行建议。",
    }
    return variants.get(case, complete)


def _span(
    trace_id: str,
    suffix: str,
    name: str,
    kind: SpanKind,
    input: dict[str, object],
    output: dict[str, object],
    error: str | None = None,
) -> Span:
    return Span(
        id=f"{trace_id}-{suffix}",
        name=name,
        kind=kind,
        input=input,
        output=output,
        duration_ms=2,
        attributes={"error": error} if error else {},
    )


def sample_traces(profile: str = "baseline") -> list[Trace]:
    if profile not in {"baseline", "optimized"}:
        raise ValueError(f"unknown sample profile: {profile}")
    cases = [
        ("trace-001", "complete", REFERENCE),
        ("trace-002", "missing_role", REFERENCE),
        ("trace-003", "missing_task", REFERENCE),
        ("trace-004", "missing_constraint", REFERENCE),
        ("trace-005", "missing_format", REFERENCE),
        ("trace-006", "complete", "建议给孩子买一台新电脑。"),
        ("trace-007", "complete", "先共情孩子。"),
        ("trace-008", "complete", REFERENCE),
    ]
    result: list[Trace] = []
    for index, (trace_id, variant, response) in enumerate(cases, 1):
        optimized = profile == "optimized"
        effective_variant = "complete" if optimized else variant
        effective_response = REFERENCE if optimized else response
        spans: list[Span] = []
        if trace_id != "trace-008" or optimized:
            spans.append(
                _span(
                    trace_id,
                    "prompt",
                    "system-prompt",
                    SpanKind.PROMPT,
                    {"prompt": _prompt(effective_variant)},
                    {},
                )
            )
        documents = [
            {
                "id": "parenting-1",
                "content": REFERENCE,
            }
        ]
        if not optimized:
            documents.append({"id": "noise-1", "content": "电脑配置与价格说明。"})
        if trace_id == "trace-007" and not optimized:
            documents = [{"id": "noise-1", "content": "电脑配置与价格说明。"}]
        spans.append(
            _span(
                trace_id,
                "retrieval",
                "knowledge",
                SpanKind.RETRIEVAL,
                {"query": "作业拖延", "top_k": 2 if not optimized else 1},
                {"documents": documents},
            )
        )
        skill_name = "general" if trace_id == "trace-002" and not optimized else "parenting"
        spans.append(
            _span(
                trace_id,
                "skill",
                skill_name,
                SpanKind.SKILL,
                {"query": "写作业拖延"},
                {"matched": optimized or trace_id != "trace-002"},
            )
        )
        tool_input: dict[str, object] = {"minutes": 20, "parts": 4}
        if trace_id == "trace-003" and not optimized:
            tool_input = {"minutes": 20, "parts": 0}
        tool_error = "division by zero" if trace_id == "trace-004" and not optimized else None
        spans.append(
            _span(
                trace_id,
                "tool",
                "task_splitter",
                SpanKind.TOOL,
                tool_input,
                {"minutes_per_part": 5} if not tool_error else {},
                tool_error,
            )
        )
        if trace_id == "trace-005" and not optimized:
            spans.append(
                _span(
                    trace_id,
                    "tool-repeat",
                    "task_splitter",
                    SpanKind.TOOL,
                    tool_input,
                    {"minutes_per_part": 5},
                )
            )
        spans.append(
            _span(
                trace_id,
                "generation",
                "generation",
                SpanKind.GENERATION,
                {},
                {"response": effective_response},
            )
        )
        citations = ["parenting-1"]
        if trace_id == "trace-006" and not optimized:
            citations = ["missing-document"]
        result.append(
            Trace(
                id=trace_id,
                query="8岁孩子写作业拖延怎么办？",
                response=effective_response,
                spans=spans,
                model="qwen2.5",
                metadata={
                    "variant": effective_variant,
                    "profile": profile,
                    "iterations": 7 if trace_id == "trace-005" and not optimized else 2,
                    "citations": citations,
                    "sequence": index,
                },
            )
        )
    return result
