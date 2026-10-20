from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from .evaluators import JudgeOutput, extract_json
from .models import Diagnosis, EvaluationResult, Severity, Trace

COMPONENTS = {
    "prompt": "Prompt",
    "g-eval": "Application",
    "rag": "RAG",
    "skill": "Skill",
    "agent": "Agent",
}

ROOT_CAUSES = {
    "role": "Prompt 缺少明确角色",
    "task": "Prompt 缺少任务定义",
    "constraint": "Prompt 缺少约束",
    "format": "Prompt 缺少输出格式",
    "faithfulness": "回答缺少 Context 支持",
    "answer_relevancy": "回答偏离参考目标",
    "context_precision": "检索上下文噪声过多",
    "context_recall": "相关文档漏召回",
    "citation_correctness": "引用不属于实际上下文",
    "skill_selection": "选择了错误 Skill",
    "skill_match": "Skill 未成功匹配",
    "tool_selection": "Agent 工具选择错误",
    "tool_arguments": "Agent 工具参数错误",
    "tool_success": "Agent 工具执行失败",
    "agent_efficiency": "Agent 重复调用或循环过多",
    "task_completion": "Agent 未完成任务",
    "overall": "最终回答质量不足",
}


def _severity(score: float) -> Severity:
    if score < 0.4:
        return Severity.HIGH
    if score < 0.7:
        return Severity.MEDIUM
    return Severity.LOW


def rule_diagnose(results: list[EvaluationResult], threshold: float = 0.7) -> list[Diagnosis]:
    """先用可重复的规则定位低分维度；LLM 归因是增强，不替代这层事实。"""
    diagnoses: list[Diagnosis] = []
    for result in results:
        if result.error or result.score >= threshold:
            continue
        weakest = min(result.dimensions, key=lambda item: item.score, default=None)
        dimension = weakest.name if weakest else result.evaluator
        root_cause = ROOT_CAUSES.get(dimension, result.reason)
        diagnoses.append(
            Diagnosis(
                trace_id=result.trace_id,
                component=COMPONENTS.get(result.evaluator, "Application"),
                severity=_severity(result.score),
                reason=result.reason,
                root_cause=root_cause,
                evidence=[dimension, *result.evidence],
                source="rule",
            )
        )
    return sorted(
        diagnoses,
        key=lambda item: (
            {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}[item.severity],
            item.component,
            item.trace_id,
        ),
    )


LLMJudge = Callable[[str], Awaitable[JudgeOutput]]


class LLMAttributor:
    def __init__(self, judge: LLMJudge):
        self.judge = judge

    async def attribute(
        self,
        traces: list[Trace],
        results: list[EvaluationResult],
        rules: list[Diagnosis],
    ) -> list[Diagnosis]:
        if not rules:
            return []
        trace_ids = {item.trace_id for item in rules}
        trace_summary = [
            {
                "trace_id": trace.id,
                "query": trace.query,
                "response": trace.response,
                "metadata": trace.metadata,
            }
            for trace in traces
            if trace.id in trace_ids
        ]
        result_summary = [
            {
                "trace_id": item.trace_id,
                "evaluator": item.evaluator,
                "score": item.score,
                "reason": item.reason,
                "dimensions": [value.model_dump() for value in item.dimensions],
            }
            for item in results
            if item.trace_id in trace_ids and item.score < 0.7
        ]
        rule_summary = [item.model_dump(mode="json") for item in rules]
        prompt = (
            "你是 AI 应用质量归因器。根据 Trace、低分结果和规则诊断，输出一个 JSON 对象，"
            "对象只有 items 字段；items 是数组，每项必须含 trace_id、component、severity、"
            "root_cause、reason、evidence。severity 只能是 high/medium/low。"
            f"\nTraces={json.dumps(trace_summary, ensure_ascii=False)}"
            f"\nResults={json.dumps(result_summary, ensure_ascii=False)}"
            f"\nRules={json.dumps(rule_summary, ensure_ascii=False)}"
        )
        raw = await self.judge(prompt)
        try:
            value = extract_json(raw.text)
            return self._parse(value)
        except Exception:
            # 结构修复只重试一次，防止 Judge 持续输出非法 JSON 形成无限循环。
            repaired = await self.judge(
                prompt + f"\n上次输出非法：{raw.text}\n只返回满足字段约束的合法 JSON。"
            )
            return self._parse(extract_json(repaired.text))

    @staticmethod
    def _parse(value: dict[str, object]) -> list[Diagnosis]:
        raw_items = value.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("attribution items must be a non-empty array")
        diagnoses: list[Diagnosis] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise ValueError("attribution item must be an object")
            diagnoses.append(
                Diagnosis(
                    trace_id=str(raw.get("trace_id", "")),
                    component=str(raw.get("component", "Application")),
                    severity=Severity(str(raw.get("severity", "medium")).lower()),
                    reason=str(raw.get("reason", "")),
                    root_cause=str(raw.get("root_cause", "")),
                    evidence=[str(item) for item in raw.get("evidence", [])]
                    if isinstance(raw.get("evidence", []), list)
                    else [],
                    source="llm",
                )
            )
        return diagnoses


def component_health(
    results: list[EvaluationResult], diagnoses: list[Diagnosis]
) -> dict[str, float]:
    scores: dict[str, list[float]] = {}
    for result in results:
        component = COMPONENTS.get(result.evaluator, "Application")
        scores.setdefault(component, []).append(result.score)
    health = {name: sum(values) / len(values) for name, values in scores.items()}
    health["overall"] = sum(result.score for result in results) / len(results) if results else 0
    return health
