from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from rich.console import Console
from rich.text import Text


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """一条不可变的评测事件；fields 保存不同步骤各自的结构化数据。"""

    run_id: str
    name: str
    fields: dict[str, Any] = field(default_factory=dict)


ColorMode = Literal["auto", "always", "never"]


class LearningTraceRenderer:
    """把评测、诊断和优化事件渲染到 stderr，不污染 stdout 的最终 JSON。"""

    _styles = {
        "config": ("⚙", "blue"),
        "trace": ("◌", "cyan"),
        "evaluation": ("◇", "yellow"),
        "evaluator": ("✓", "bright_green"),
        "judge": ("◎", "magenta"),
        "report": ("▣", "bright_blue"),
        "comparison": ("⇄", "bright_cyan"),
        "diagnosis": ("⌕", "bright_yellow"),
        "optimization": ("◆", "bright_magenta"),
        "gate": ("☑", "green"),
        "loop": ("↻", "blue"),
    }

    def __init__(self, *, color: ColorMode = "auto", console: Console | None = None) -> None:
        self.console = console or Console(
            stderr=True,
            force_terminal=True if color == "always" else None,
            no_color=True if color == "never" else False if color == "always" else None,
            highlight=False,
            soft_wrap=True,
        )

    def __call__(self, event: TraceEvent) -> None:
        domain = event.name.split(".", 1)[0]
        icon, style = self._styles.get(domain, ("•", "white"))
        if event.name.endswith(("failed", "error")) or event.fields.get("status") == "failed":
            icon, style = "✗", "red"
        elif event.name.endswith(("finish", "ready", "written")):
            icon, style = "✓", "green"
        line = Text()
        line.append(f"{icon} {event.name:<26}", style=f"bold {style}")
        line.append(json.dumps(event.fields, ensure_ascii=False, default=str))
        line.append("  ")
        line.append(f"run={event.run_id}", style="dim")
        self.console.print(line)
