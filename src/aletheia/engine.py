from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable

from .evaluators import EvaluatorRegistry
from .models import (
    EvaluationCase,
    EvaluationResult,
    EvaluationSummary,
    Trace,
)
from .observability import TraceEvent


class EvaluationEngine:
    def __init__(
        self,
        registry: EvaluatorRegistry,
        max_concurrency: int = 4,
        trace_observer: Callable[[TraceEvent], None] | None = None,
        run_id: str = "evaluation",
    ):
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        self.registry = registry
        self.max_concurrency = max_concurrency
        self.trace_observer = trace_observer
        self.run_id = run_id

    def _emit(self, name: str, **fields: object) -> None:
        if self.trace_observer is not None:
            self.trace_observer(TraceEvent(self.run_id, name, fields))

    async def run(self, traces: list[Trace], cases: list[EvaluationCase]) -> list[EvaluationResult]:
        trace_by_id = {trace.id: trace for trace in traces}
        if len(trace_by_id) != len(traces):
            raise ValueError("trace ids must be unique")
        semaphore = asyncio.Semaphore(self.max_concurrency)
        jobs: list[tuple[Trace, EvaluationCase, str]] = []
        for case in cases:
            if case.trace_id not in trace_by_id:
                raise ValueError(f"case {case.id} references unknown trace {case.trace_id}")
            for evaluator_name in case.evaluators:
                jobs.append((trace_by_id[case.trace_id], case, evaluator_name))
        self._emit(
            "evaluation.start",
            traces=len(traces),
            cases=len(cases),
            jobs=len(jobs),
            max_concurrency=self.max_concurrency,
        )

        async def run_one(
            trace: Trace, case: EvaluationCase, evaluator_name: str
        ) -> EvaluationResult:
            try:
                self._emit(
                    "evaluator.start",
                    trace_id=trace.id,
                    case_id=case.id,
                    evaluator=evaluator_name,
                )
                # Semaphore 是并发闸门：任务都已创建，但同时最多只有指定数量进入评测器。
                async with semaphore:
                    result = await self.registry.get(evaluator_name).evaluate(trace, case)
                self._emit(
                    "evaluator.finish",
                    trace_id=trace.id,
                    case_id=case.id,
                    evaluator=evaluator_name,
                    score=round(result.score, 4),
                    degraded=result.degraded,
                )
                return result
            except Exception as exc:
                self._emit(
                    "evaluator.failed",
                    trace_id=trace.id,
                    case_id=case.id,
                    evaluator=evaluator_name,
                    error=f"{type(exc).__name__}: {exc}",
                )
                return EvaluationResult(
                    trace_id=trace.id,
                    case_id=case.id,
                    evaluator=evaluator_name,
                    score=0,
                    reason="Evaluator 执行失败",
                    error=f"{type(exc).__name__}: {exc}",
                    degraded=True,
                )

        # gather 保留 jobs 的输入顺序，所以并发完成顺序不会打乱最终报告。
        results = list(await asyncio.gather(*(run_one(*job) for job in jobs)))
        self._emit(
            "evaluation.finish",
            results=len(results),
            failed=sum(result.error is not None for result in results),
        )
        return results


def summarize(
    results: list[EvaluationResult], total_cases: int, pass_score: float
) -> EvaluationSummary:
    evaluator_scores: defaultdict[str, list[float]] = defaultdict(list)
    dimension_scores: defaultdict[str, list[float]] = defaultdict(list)
    for result in results:
        if not result.error:
            evaluator_scores[result.evaluator].append(result.score)
            for dimension in result.dimensions:
                dimension_scores[dimension.name].append(dimension.score)
    successful = sum(result.error is None for result in results)
    passed = sum(result.error is None and result.score >= pass_score for result in results)
    return EvaluationSummary(
        total_cases=total_cases,
        successful_results=successful,
        failed_results=len(results) - successful,
        pass_rate=passed / len(results) if results else 0,
        evaluator_means={
            name: sum(values) / len(values) for name, values in evaluator_scores.items()
        },
        dimension_means={
            name: sum(values) / len(values) for name, values in dimension_scores.items()
        },
    )


def compare_summaries(
    before: EvaluationSummary, after: EvaluationSummary
) -> dict[str, dict[str, float]]:
    evaluator_names = sorted(before.evaluator_means.keys() | after.evaluator_means.keys())
    dimension_names = sorted(before.dimension_means.keys() | after.dimension_means.keys())
    return {
        "evaluators": {
            name: after.evaluator_means.get(name, 0) - before.evaluator_means.get(name, 0)
            for name in evaluator_names
        },
        "dimensions": {
            name: after.dimension_means.get(name, 0) - before.dimension_means.get(name, 0)
            for name in dimension_names
        },
        "overall": {"pass_rate": after.pass_rate - before.pass_rate},
    }
