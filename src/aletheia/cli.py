from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .config import AppConfig
from .diagnosis import LLMAttributor, component_health, rule_diagnose
from .engine import EvaluationEngine, compare_summaries, summarize
from .evaluators import (
    AgentEvaluator,
    EvaluatorRegistry,
    GEvalEvaluator,
    PromptEvaluator,
    RAGEvaluator,
    SkillEvaluator,
)
from .judge import OllamaJudge
from .models import (
    Diagnosis,
    EvaluationCase,
    EvaluationResult,
    EvaluationRun,
    EvaluationSummary,
    RunManifest,
    Trace,
)
from .observability import LearningTraceRenderer, TraceEvent
from .optimization import acceptance_gates, build_tasks
from .reporting import write_diagnosis_bundle, write_run, write_tasks_bundle
from .sample_app import sample_traces
from .storage import JsonlTraceStore, load_cases


def run_id(prefix: str = "run") -> str:
    return datetime.now(UTC).strftime(f"{prefix}-%Y%m%dT%H%M%S-%fZ")


def stage_cases(cases: list[EvaluationCase], stage: int) -> list[EvaluationCase]:
    if stage == 1:
        return cases
    evaluators = ["prompt", "g-eval", "rag", "skill", "agent"]
    return [case.model_copy(update={"evaluators": evaluators}) for case in cases]


async def evaluate_run(
    config: AppConfig,
    stage: int,
    traces: list[Trace],
    cases: list[EvaluationCase],
    profile: str,
    trace_observer: Callable[[TraceEvent], None] | None = None,
) -> tuple[EvaluationRun, Path]:
    judge = OllamaJudge(config)
    started = datetime.now(UTC)
    identifier = run_id(f"stage{stage}-{profile}")
    if trace_observer is not None:
        trace_observer(
            TraceEvent(
                identifier,
                "config.ready",
                {
                    "stage": stage,
                    "profile": profile,
                    "judge": config.judge.model,
                    "max_concurrency": config.runtime.max_concurrency,
                },
            )
        )
    try:
        evaluators = [PromptEvaluator(), GEvalEvaluator(judge)]
        if stage >= 2:
            evaluators.extend([RAGEvaluator(), SkillEvaluator(), AgentEvaluator()])
        registry = EvaluatorRegistry(evaluators)
        selected_cases = stage_cases(cases, stage)
        results = await EvaluationEngine(
            registry,
            config.runtime.max_concurrency,
            trace_observer,
            identifier,
        ).run(traces, selected_cases)
    finally:
        await judge.close()
    summary = summarize(results, len(cases), config.thresholds.pass_score)
    digest = hashlib.sha256(config.data.evaluation_set.read_bytes()).hexdigest()
    manifest = RunManifest(
        run_id=identifier,
        stage=stage,
        started_at=started,
        completed_at=datetime.now(UTC),
        model=config.judge.model,
        evaluation_set_sha256=digest,
        trace_count=len(traces),
        evaluators=registry.names,
        successful_results=summary.successful_results,
        failed_results=summary.failed_results,
        config={**config.model_dump(mode="json"), "profile": profile},
    )
    run = EvaluationRun(manifest=manifest, summary=summary, results=results)
    directory = write_run(config.output.directory, run, traces)
    if trace_observer is not None:
        trace_observer(
            TraceEvent(
                identifier,
                "report.written",
                {
                    "directory": str(directory),
                    "pass_rate": round(summary.pass_rate, 4),
                    "successful": summary.successful_results,
                    "failed": summary.failed_results,
                },
            )
        )
    return run, directory


def write_comparison(output: Path, before: EvaluationRun, after: EvaluationRun, mode: str) -> Path:
    directory = output / run_id("comparison")
    directory.mkdir(parents=True, exist_ok=False)
    deltas = compare_summaries(before.summary, after.summary)
    payload = {
        "before_run_id": before.manifest.run_id,
        "after_run_id": after.manifest.run_id,
        "mode": mode,
        "before": before.summary.model_dump(),
        "after": after.summary.model_dump(),
        "delta": deltas,
    }
    (directory / "comparison.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Evaluation Comparison",
        "",
        f"- Before: `{before.manifest.run_id}`",
        f"- After: `{after.manifest.run_id}`",
        f"- Mode: `{mode}`",
        "",
        "| Evaluator | Before | After | Delta |",
        "|---|---:|---:|---:|",
    ]
    for name in sorted(
        before.summary.evaluator_means.keys() | after.summary.evaluator_means.keys()
    ):
        left = before.summary.evaluator_means.get(name, 0)
        right = after.summary.evaluator_means.get(name, 0)
        lines.append(f"| {name} | {left:.3f} | {right:.3f} | {right - left:+.3f} |")
    (directory / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


def load_run(output: Path, identifier: str) -> tuple[EvaluationRun, list[Trace]]:
    directory = output / identifier
    manifest = RunManifest.model_validate_json(
        (directory / "manifest.json").read_text(encoding="utf-8")
    )
    summary = EvaluationSummary.model_validate_json(
        (directory / "evaluation-summary.json").read_text(encoding="utf-8")
    )
    raw_results = json.loads((directory / "evaluation-results.json").read_text(encoding="utf-8"))
    results = [EvaluationResult.model_validate(item) for item in raw_results]
    traces = JsonlTraceStore(directory / "traces.jsonl").read_all()
    return EvaluationRun(manifest=manifest, summary=summary, results=results), traces


def close_existing_loop(
    output: Path,
    before_id: str,
    after_id: str,
    diagnosis_id: str,
    optimization_id: str,
) -> tuple[Path, dict[str, object]]:
    before, _ = load_run(output, before_id)
    after, _ = load_run(output, after_id)
    if before.manifest.evaluation_set_sha256 != after.manifest.evaluation_set_sha256:
        raise ValueError("before and after evaluation set hashes differ")
    if before.manifest.model != after.manifest.model:
        raise ValueError("before and after judge models differ")
    diagnosis_source = (
        (output / diagnosis_id / "source-run.txt").read_text(encoding="utf-8").strip()
    )
    if diagnosis_source != before_id:
        raise ValueError("diagnosis does not reference the before run")
    optimization_source = (
        (output / optimization_id / "source-diagnosis.txt").read_text(encoding="utf-8").strip()
    )
    if optimization_source != diagnosis_id:
        raise ValueError("optimization does not reference the diagnosis")
    gates = acceptance_gates(before.summary.evaluator_means, after.summary.evaluator_means)
    payload: dict[str, object] = {
        "before_run_id": before_id,
        "diagnosis_id": diagnosis_id,
        "optimization_id": optimization_id,
        "after_run_id": after_id,
        "evaluation_set_sha256": before.manifest.evaluation_set_sha256,
        "judge_model": before.manifest.model,
        "gates": gates,
        "accepted": all(gates.values()),
        "delta": compare_summaries(before.summary, after.summary),
    }
    directory = output / run_id("closed-loop")
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "loop.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Closed Optimization Loop",
        "",
        f"- Before: `{before_id}`",
        f"- Diagnosis: `{diagnosis_id}`",
        f"- Optimization: `{optimization_id}`",
        f"- After: `{after_id}`",
        f"- Accepted: `{all(gates.values())}`",
        "",
        "| Gate | Result |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {'PASS' if passed else 'FAIL'} |" for name, passed in gates.items())
    (directory / "loop.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory, payload


async def diagnose_run(
    config: AppConfig,
    run: EvaluationRun,
    traces: list[Trace],
    directory: Path,
    trace_observer: Callable[[TraceEvent], None] | None = None,
    trace_run_id: str = "diagnosis",
) -> tuple[list[Diagnosis], list[Diagnosis]]:
    rules = rule_diagnose(run.results, config.thresholds.pass_score)
    if trace_observer is not None:
        trace_observer(
            TraceEvent(trace_run_id, "diagnosis.rules_finish", {"diagnoses": len(rules)})
        )
    judge = OllamaJudge(config)
    try:
        if trace_observer is not None:
            trace_observer(TraceEvent(trace_run_id, "judge.start", {"operation": "attribution"}))
        llm = await LLMAttributor(judge).attribute(traces, run.results, rules)
        if trace_observer is not None:
            trace_observer(TraceEvent(trace_run_id, "judge.finish", {"diagnoses": len(llm)}))
    finally:
        await judge.close()
    write_diagnosis_bundle(directory, rules, llm, component_health(run.results, rules))
    return rules, llm


async def execute(args: argparse.Namespace) -> None:
    config = AppConfig.from_yaml(args.config)
    renderer = (
        LearningTraceRenderer(color=config.observability.color)
        if config.observability.enabled
        else None
    )
    command_run_id = run_id(args.command)

    def emit(name: str, **fields: object) -> None:
        if renderer is not None:
            renderer(TraceEvent(command_run_id, name, fields))

    emit(
        "config.ready",
        command=args.command,
        judge=config.judge.model,
        traces=str(config.data.traces),
        cases=str(config.data.evaluation_set),
    )
    store = JsonlTraceStore(config.data.traces)
    if args.command == "record":
        emit("trace.record_start", profile=args.profile)
        traces = sample_traces(args.profile)
        store.replace(traces)
        emit("trace.record_finish", traces=len(traces), path=str(store.path))
        print(
            json.dumps({"recorded": len(traces), "profile": args.profile, "path": str(store.path)})
        )
        return
    cases = load_cases(config.data.evaluation_set)
    if args.command == "status":
        trace_count = len(store.read_all())
        emit("trace.loaded", traces=trace_count, cases=len(cases))
        print(
            json.dumps(
                {
                    "model": config.llm.model,
                    "judge": config.judge.model,
                    "traces": trace_count,
                    "cases": len(cases),
                    "output": str(config.output.directory),
                    "max_concurrency": config.runtime.max_concurrency,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.command == "eval":
        traces = store.read_all()
        profile = str(traces[0].metadata.get("profile", "recorded")) if traces else "empty"
        run, directory = await evaluate_run(config, args.stage, traces, cases, profile, renderer)
        print(
            json.dumps(
                {
                    **run.summary.model_dump(),
                    "run_id": run.manifest.run_id,
                    "output": str(directory),
                }
            )
        )
        return
    if args.command == "compare":
        if args.mode == "model":
            before_config = config.model_copy(
                update={"judge": config.judge.model_copy(update={"model": args.before_model})}
            )
            after_config = config.model_copy(
                update={"judge": config.judge.model_copy(update={"model": args.after_model})}
            )
            before_profile = after_profile = "optimized"
        else:
            before_config = after_config = config
            before_profile, after_profile = "baseline", "optimized"
        before, before_path = await evaluate_run(
            before_config,
            2,
            sample_traces(before_profile),
            cases,
            f"{before_profile}-{before_config.judge.model}",
            renderer,
        )
        after, after_path = await evaluate_run(
            after_config,
            2,
            sample_traces(after_profile),
            cases,
            f"{after_profile}-{after_config.judge.model}",
            renderer,
        )
        comparison = write_comparison(config.output.directory, before, after, args.mode)
        emit(
            "comparison.finish",
            mode=args.mode,
            before=before.manifest.run_id,
            after=after.manifest.run_id,
            directory=str(comparison),
        )
        print(
            json.dumps(
                {
                    "before": str(before_path),
                    "after": str(after_path),
                    "comparison": str(comparison),
                    "mode": args.mode,
                    "delta": compare_summaries(before.summary, after.summary),
                },
                ensure_ascii=False,
            )
        )
        return
    if args.command == "diagnose":
        emit("diagnosis.start", source_run=args.run_id)
        run, traces = load_run(config.output.directory, args.run_id)
        directory = config.output.directory / run_id("diagnosis")
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "source-run.txt").write_text(run.manifest.run_id + "\n", encoding="utf-8")
        rules, llm = await diagnose_run(config, run, traces, directory, renderer, command_run_id)
        emit(
            "diagnosis.finish",
            rules=len(rules),
            llm=len(llm),
            directory=str(directory),
        )
        print(
            json.dumps(
                {"output": str(directory), "rule_diagnoses": len(rules), "llm_diagnoses": len(llm)}
            )
        )
        return
    if args.command == "optimize":
        emit("optimization.start", diagnosis=args.diagnosis_id)
        source = config.output.directory / args.diagnosis_id / "diagnosis.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        raw_items = [
            *(payload.get("rule_diagnoses") or []),
            *(payload.get("llm_diagnoses") or []),
        ]
        diagnoses = [Diagnosis.model_validate(item) for item in raw_items]
        tasks = build_tasks(diagnoses)
        directory = config.output.directory / run_id("optimization")
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "source-diagnosis.txt").write_text(args.diagnosis_id + "\n", encoding="utf-8")
        write_tasks_bundle(directory, tasks)
        emit("optimization.finish", tasks=len(tasks), directory=str(directory))
        print(json.dumps({"output": str(directory), "tasks": len(tasks)}))
        return
    if args.command == "loop":
        emit("loop.start", stage=3)
        directory = config.output.directory / run_id("loop")
        directory.mkdir(parents=True, exist_ok=False)
        before, before_path = await evaluate_run(
            config, 3, sample_traces("baseline"), cases, "baseline", renderer
        )
        rules, llm = await diagnose_run(
            config,
            before,
            sample_traces("baseline"),
            directory,
            renderer,
            command_run_id,
        )
        tasks = build_tasks([*rules, *llm])
        write_tasks_bundle(directory, tasks)
        after, after_path = await evaluate_run(
            config, 3, sample_traces("optimized"), cases, "optimized", renderer
        )
        comparison = write_comparison(config.output.directory, before, after, "loop")
        gates = acceptance_gates(before.summary.evaluator_means, after.summary.evaluator_means)
        for name, passed in gates.items():
            emit("gate.finish", gate=name, passed=passed)
        loop_payload = {
            "before_run_id": before.manifest.run_id,
            "after_run_id": after.manifest.run_id,
            "comparison": comparison.name,
            "rule_diagnoses": len(rules),
            "llm_diagnoses": len(llm),
            "tasks": len(tasks),
            "gates": gates,
            "accepted": all(gates.values()),
        }
        (directory / "loop.json").write_text(
            json.dumps(loop_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (directory / "loop.md").write_text(
            "# Optimization Loop\n\n"
            f"- Before: `{before_path.name}`\n- After: `{after_path.name}`\n"
            f"- Comparison: `{comparison.name}`\n- Accepted: `{all(gates.values())}`\n",
            encoding="utf-8",
        )
        print(json.dumps({"output": str(directory), **loop_payload}, ensure_ascii=False))
        emit("loop.finish", accepted=all(gates.values()), directory=str(directory))
        return
    if args.command == "close-loop":
        directory, payload = close_existing_loop(
            config.output.directory,
            args.before_run,
            args.after_run,
            args.diagnosis_id,
            args.optimization_id,
        )
        print(json.dumps({"output": str(directory), **payload}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="aletheia Python")
    parser.add_argument("--config", type=Path, default=Path("config/local.yaml"))
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record")
    record.add_argument("--profile", choices=["baseline", "optimized"], default="baseline")
    sub.add_parser("status")
    evaluate = sub.add_parser("eval")
    evaluate.add_argument("stage", type=int, choices=[1, 2, 3])
    compare = sub.add_parser("compare")
    compare.add_argument("--mode", choices=["config", "model"], default="config")
    compare.add_argument("--before-model", default="qwen2.5:3b")
    compare.add_argument("--after-model", default="qwen2.5:7b")
    diagnose = sub.add_parser("diagnose")
    diagnose.add_argument("--run-id", required=True)
    optimize = sub.add_parser("optimize")
    optimize.add_argument("--diagnosis-id", required=True)
    sub.add_parser("loop")
    close_loop = sub.add_parser("close-loop")
    close_loop.add_argument("--before-run", required=True)
    close_loop.add_argument("--after-run", required=True)
    close_loop.add_argument("--diagnosis-id", required=True)
    close_loop.add_argument("--optimization-id", required=True)
    return parser


def main() -> None:
    asyncio.run(execute(build_parser().parse_args()))
