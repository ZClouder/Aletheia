from __future__ import annotations

import json
import math
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from .models import DimensionScore, EvaluationCase, EvaluationResult, SpanKind, Trace


@dataclass(frozen=True, slots=True)
class JudgeOutput:
    text: str
    top_logprobs: dict[str, float]


Judge = Callable[[str], Awaitable[JudgeOutput]]


class Evaluator(Protocol):
    """Protocol 只声明能力，不强制实现类继承，便于测试传入轻量 Fake。"""

    name: str

    async def evaluate(self, trace: Trace, case: EvaluationCase) -> EvaluationResult: ...


def extract_json(text: str) -> dict[str, object]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("judge response contains no JSON object")
    value = json.loads(match.group())
    if not isinstance(value, dict):
        raise ValueError("judge JSON must be an object")
    return value


def normalized_logprob_score(top_logprobs: dict[str, float]) -> float:
    """把 1–5 分 token 的对数概率转回概率，再计算归一化期望分。"""
    probabilities: dict[int, float] = {}
    for token, logprob in top_logprobs.items():
        match = re.search(r"(?<!\d)([1-5])(?!\d)", token.strip())
        if match:
            score = int(match.group(1))
            # 模型返回 log(p)；math.exp(logprob) 把它还原为普通概率 p。
            probabilities[score] = probabilities.get(score, 0) + math.exp(logprob)
    total = sum(probabilities.values())
    if not total:
        raise ValueError("judge logprobs contain no score token from 1 to 5")
    expected = sum(score * probability for score, probability in probabilities.items()) / total
    return (expected - 1) / 4


class PromptEvaluator:
    name = "prompt"
    DIMENSIONS = {
        "role": ("你是", "角色"),
        "task": ("请", "任务", "回答"),
        "constraint": ("必须", "不要", "仅", "禁止"),
        "format": ("格式", "JSON", "列表", "三点", "三个"),
    }

    async def evaluate(self, trace: Trace, case: EvaluationCase) -> EvaluationResult:
        prompt_spans = [span for span in trace.spans if span.kind is SpanKind.PROMPT]
        if not prompt_spans:
            return EvaluationResult(
                trace_id=trace.id,
                case_id=case.id,
                evaluator=self.name,
                score=0,
                reason="缺少 Prompt Span",
                evidence=["prompt span absent"],
                dimensions=[
                    DimensionScore(name=name, score=0, reason="Prompt Span 缺失")
                    for name in self.DIMENSIONS
                ],
            )
        prompt = str(prompt_spans[-1].input.get("prompt", ""))
        dimensions = [
            DimensionScore(
                name=name,
                score=float(any(word in prompt for word in words)),
                reason="命中结构标记" if any(word in prompt for word in words) else "缺少结构标记",
            )
            for name, words in self.DIMENSIONS.items()
        ]
        score = sum(item.score for item in dimensions) / len(dimensions)
        missing = [item.name for item in dimensions if item.score == 0]
        return EvaluationResult(
            trace_id=trace.id,
            case_id=case.id,
            evaluator=self.name,
            score=score,
            reason="Prompt 结构完整" if not missing else "缺少 " + "、".join(missing),
            evidence=missing,
            dimensions=dimensions,
        )


class GEvalEvaluator:
    name = "g-eval"

    def __init__(self, judge: Judge):
        self.judge = judge

    async def evaluate(self, trace: Trace, case: EvaluationCase) -> EvaluationResult:
        criteria = (
            "正确性：与参考答案一致；相关性：直接回答问题；完整性：覆盖参考答案关键事实。"
            "参考答案定义完整性边界；若已覆盖其全部要点，不得因缺少参考答案之外的展开扣分。"
        )
        analysis_prompt = (
            f"评测标准：{criteria}\n问题：{trace.query}\n参考答案：{case.reference_answer}\n"
            f"待评回答：{trace.response}\n先逐步比较，再只返回一个 JSON 对象。"
            "对象必须含字符串字段 reason 和字符串数组字段 evidence；"
            "reason 必须写出本题的具体判断，不得复述字段说明。"
        )
        raw_analysis = await self.judge(analysis_prompt)
        try:
            analysis = extract_json(raw_analysis.text)
        except (json.JSONDecodeError, ValueError):
            # 第一次 JSON 不合法时只修复一次；仍失败就向上抛出，由 Engine 记录 degraded。
            repaired = await self.judge(
                analysis_prompt + f"\n上次输出非法：{raw_analysis.text}\n只返回合法 JSON。"
            )
            analysis = extract_json(repaired.text)
            raw_analysis = repaired
        reason = str(analysis.get("reason", ""))
        raw_evidence = analysis.get("evidence", [])
        evidence = (
            [str(item) for item in raw_evidence]
            if isinstance(raw_evidence, list)
            else [str(raw_evidence)]
        )
        scoring = await self.judge(
            f"评测标准：{criteria}\n问题：{trace.query}\n参考答案：{case.reference_answer}\n"
            f"待评回答：{trace.response}\n分析：{reason}\n"
            "给出 1 到 5 的一个整数分数，只输出数字。"
        )
        try:
            score = normalized_logprob_score(scoring.top_logprobs)
            degraded = False
        except ValueError:
            match = re.search(r"(?<!\d)([1-5])(?!\d)", scoring.text)
            if not match:
                raise ValueError(
                    "judge returned neither score logprobs nor a score token"
                ) from None
            score = (int(match.group(1)) - 1) / 4
            degraded = True
        return EvaluationResult(
            trace_id=trace.id,
            case_id=case.id,
            evaluator=self.name,
            score=score,
            reason=reason,
            evidence=evidence,
            dimensions=[DimensionScore(name="overall", score=score, reason=reason)],
            degraded=degraded,
            raw_judge=f"analysis={raw_analysis.text}\nscore={scoring.text}",
        )


def _content_tokens(text: str) -> set[str]:
    chinese = set(re.findall(r"[\u4e00-\u9fff]", text))
    words = set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))
    return chinese | words


def _overlap(left: str, right: str) -> float:
    left_tokens = _content_tokens(left)
    if not left_tokens:
        return 0
    return len(left_tokens & _content_tokens(right)) / len(left_tokens)


class RAGEvaluator:
    name = "rag"

    async def evaluate(self, trace: Trace, case: EvaluationCase) -> EvaluationResult:
        retrievals = [span for span in trace.spans if span.kind is SpanKind.RETRIEVAL]
        if not retrievals:
            return EvaluationResult(
                trace_id=trace.id,
                case_id=case.id,
                evaluator=self.name,
                score=0,
                reason="缺少 Retrieval Span",
                evidence=["retrieval span absent"],
            )
        raw_documents = retrievals[-1].output.get("documents", [])
        documents = raw_documents if isinstance(raw_documents, list) else []
        document_ids = [str(item.get("id", "")) for item in documents if isinstance(item, dict)]
        context = " ".join(
            str(item.get("content", "")) for item in documents if isinstance(item, dict)
        )
        expected_ids = {str(item) for item in case.expected.get("relevant_document_ids", [])}
        found = expected_ids.intersection(document_ids)
        precision = len(found) / len(document_ids) if document_ids else 0
        recall = len(found) / len(expected_ids) if expected_ids else 0
        faithfulness = _overlap(trace.response, context)
        relevancy = _overlap(trace.response, case.reference_answer)
        citations = [str(item) for item in trace.metadata.get("citations", [])]
        citation = float(bool(citations) and set(citations).issubset(set(document_ids)))
        dimensions = [
            DimensionScore(name="faithfulness", score=faithfulness),
            DimensionScore(name="answer_relevancy", score=relevancy),
            DimensionScore(name="context_precision", score=precision),
            DimensionScore(name="context_recall", score=recall),
            DimensionScore(name="citation_correctness", score=citation),
        ]
        score = sum(item.score for item in dimensions) / len(dimensions)
        return EvaluationResult(
            trace_id=trace.id,
            case_id=case.id,
            evaluator=self.name,
            score=score,
            reason="RAG 五维规则评测",
            evidence=sorted(found),
            dimensions=dimensions,
        )


class SkillEvaluator:
    name = "skill"

    async def evaluate(self, trace: Trace, case: EvaluationCase) -> EvaluationResult:
        spans = [span for span in trace.spans if span.kind is SpanKind.SKILL]
        expected = str(case.expected.get("skill", ""))
        selected = spans[-1].name if spans else ""
        matched = bool(spans and spans[-1].output.get("matched"))
        selection = float(bool(expected) and selected == expected)
        match_score = float(matched)
        dimensions = [
            DimensionScore(name="skill_selection", score=selection),
            DimensionScore(name="skill_match", score=match_score),
        ]
        return EvaluationResult(
            trace_id=trace.id,
            case_id=case.id,
            evaluator=self.name,
            score=(selection + match_score) / 2,
            reason="Skill 选择与匹配正确" if selection and matched else "Skill 选择或匹配错误",
            evidence=[f"expected={expected}", f"selected={selected}"],
            dimensions=dimensions,
        )


class AgentEvaluator:
    name = "agent"

    async def evaluate(self, trace: Trace, case: EvaluationCase) -> EvaluationResult:
        tools = [span for span in trace.spans if span.kind is SpanKind.TOOL]
        expected_tools = [str(item) for item in case.expected.get("tools", [])]
        actual_tools = [span.name for span in tools]
        selection = float(actual_tools == expected_tools)
        expected_args = case.expected.get("tool_args", {})
        arguments = float(
            isinstance(expected_args, dict)
            and all(
                span.input == expected_args.get(span.name, {})
                for span in tools
                if span.name in expected_args
            )
            and len(tools) == len(expected_tools)
        )
        success = float(not any(span.attributes.get("error") for span in tools))
        iterations = int(trace.metadata.get("iterations", 1))
        repeated = len(actual_tools) != len(set(actual_tools))
        efficiency = float(iterations <= 5 and not repeated)
        completion = _overlap(trace.response, case.reference_answer)
        dimensions = [
            DimensionScore(name="tool_selection", score=selection),
            DimensionScore(name="tool_arguments", score=arguments),
            DimensionScore(name="tool_success", score=success),
            DimensionScore(name="agent_efficiency", score=efficiency),
            DimensionScore(name="task_completion", score=completion),
        ]
        score = sum(item.score for item in dimensions) / len(dimensions)
        return EvaluationResult(
            trace_id=trace.id,
            case_id=case.id,
            evaluator=self.name,
            score=score,
            reason="Agent 工具、参数、恢复、效率与完成度评测",
            evidence=[f"expected={expected_tools}", f"actual={actual_tools}"],
            dimensions=dimensions,
        )


class EvaluatorRegistry:
    """按稳定名称保存 Evaluator，避免 CLI 用 if/elif 硬编码每个实现。"""

    def __init__(self, evaluators: list[Evaluator]):
        self._items = {evaluator.name: evaluator for evaluator in evaluators}
        if len(self._items) != len(evaluators):
            raise ValueError("evaluator names must be unique")

    @property
    def names(self) -> list[str]:
        return sorted(self._items)

    def get(self, name: str) -> Evaluator:
        try:
            return self._items[name]
        except KeyError as exc:
            raise ValueError(f"unknown evaluator: {name}") from exc
