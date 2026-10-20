from __future__ import annotations

import json
from pathlib import Path

from .models import Diagnosis, EvaluationRun, OptimizationTask, Trace


def evaluation_markdown(run: EvaluationRun) -> str:
    summary = run.summary
    lines = [
        f"# Evaluation Run {run.manifest.run_id}",
        "",
        f"- Stage: {run.manifest.stage}",
        f"- Model: {run.manifest.model}",
        f"- Cases: {summary.total_cases}",
        f"- Successful results: {summary.successful_results}",
        f"- Failed results: {summary.failed_results}",
        f"- Pass rate: {summary.pass_rate:.3f}",
        "",
        "## Evaluator Means",
        "",
        "| Evaluator | Score |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {name} | {score:.3f} |" for name, score in sorted(summary.evaluator_means.items())
    )
    lines.extend(
        [
            "",
            "## Dimension Means",
            "",
            "| Dimension | Score |",
            "|---|---:|",
        ]
    )
    lines.extend(
        f"| {name} | {score:.3f} |" for name, score in sorted(summary.dimension_means.items())
    )
    lines.extend(
        [
            "",
            "## Details",
            "",
            "| Case | Trace | Evaluator | Score | Degraded | Result |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    lines.extend(
        f"| {item.case_id} | {item.trace_id} | {item.evaluator} | {item.score:.3f} | "
        f"{'yes' if item.degraded else 'no'} | {item.error or item.reason} |"
        for item in run.results
    )
    return "\n".join(lines) + "\n"


def write_run(directory: Path, run: EvaluationRun, traces: list[Trace]) -> Path:
    run_directory = directory / run.manifest.run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    (run_directory / "manifest.json").write_text(
        run.manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (run_directory / "traces.jsonl").write_text(
        "".join(trace.model_dump_json() + "\n" for trace in traces), encoding="utf-8"
    )
    (run_directory / "evaluation-results.json").write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in run.results],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_directory / "evaluation-summary.json").write_text(
        run.summary.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (run_directory / "evaluation-report.md").write_text(evaluation_markdown(run), encoding="utf-8")
    return run_directory


def write_diagnosis_bundle(
    directory: Path,
    rules: list[Diagnosis],
    llm: list[Diagnosis],
    health: dict[str, float],
) -> None:
    payload = {
        "health": health,
        "diagnosis_count": len(rules),
        "rule_diagnoses": [item.model_dump(mode="json") for item in rules],
        "llm_diagnoses": [item.model_dump(mode="json") for item in llm],
    }
    (directory / "diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = ["# Diagnosis", "", "## Health", "", "| Component | Score |", "|---|---:|"]
    lines.extend(f"| {name} | {score:.3f} |" for name, score in sorted(health.items()))
    lines.extend(["", f"Rule diagnosis count: **{len(rules)}**"])
    lines.extend(["", "## Rule Bottlenecks", ""])
    lines.extend(
        f"- **{item.severity.value} · {item.component}** `{item.trace_id}`："
        f"{item.root_cause}（{item.reason}）"
        for item in rules
    )
    lines.extend(["", "## LLM Attribution", ""])
    lines.extend(
        f"- **{item.severity.value} · {item.component}** `{item.trace_id}`："
        f"{item.root_cause}（{item.reason}）"
        for item in llm
    )
    (directory / "diagnosis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tasks_bundle(directory: Path, tasks: list[OptimizationTask]) -> None:
    (directory / "optimization-tasks.json").write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in tasks],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    lines = ["# Optimization Tasks", ""]
    for index, item in enumerate(tasks, 1):
        lines.extend(
            [
                f"## {index}. [{item.priority.value}] {item.title}",
                "",
                item.action,
                "",
                "证据：" + "；".join(item.evidence),
                "",
                f"验收：`{item.acceptance_metric}`",
                "",
            ]
        )
    (directory / "optimization-tasks.md").write_text("\n".join(lines), encoding="utf-8")
