from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .models import EvaluationCase, Trace


class JsonlTraceStore:
    """JSONL 每行保存一个完整 Trace，适合追加、流式读取和定位坏行。"""

    def __init__(self, path: Path):
        self.path = path

    def append(self, trace: Trace) -> None:
        existing_ids = {item.id for item in self.read_all()}
        if trace.id in existing_ids:
            raise ValueError(f"duplicate trace id: {trace.id}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(trace.model_dump_json() + "\n")

    def replace(self, traces: list[Trace]) -> None:
        ids = [trace.id for trace in traces]
        if len(ids) != len(set(ids)):
            raise ValueError("trace ids must be unique")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = "".join(trace.model_dump_json() + "\n" for trace in traces)
        self.path.write_text(content, encoding="utf-8")

    def read_all(self) -> list[Trace]:
        if not self.path.exists():
            return []
        traces: list[Trace] = []
        seen: set[str] = set()
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            # enumerate(..., 1) 让错误行号从人类习惯的 1 开始，而不是 Python 的 0。
            if not line.strip():
                continue
            try:
                trace = Trace.model_validate_json(line)
            except (ValidationError, ValueError) as exc:
                raise ValueError(f"invalid trace at line {line_number}: {exc}") from exc
            if trace.id in seen:
                raise ValueError(f"duplicate trace id at line {line_number}: {trace.id}")
            seen.add(trace.id)
            traces.append(trace)
        return traces


def load_cases(path: Path) -> list[EvaluationCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("evaluation set must be a non-empty JSON array")
    cases = [EvaluationCase.model_validate(item) for item in raw]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("evaluation case ids must be unique")
    return cases
