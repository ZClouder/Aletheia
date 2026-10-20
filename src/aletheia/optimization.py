from __future__ import annotations

from collections import defaultdict

from .models import Diagnosis, OptimizationTask, Severity

ACTIONS = {
    "Prompt": "补齐角色、任务、约束与格式，并用固定 Case 复测。",
    "RAG": "调整召回、去噪、引用与上下文使用，复测 RAG 五维。",
    "Skill": "修正 Skill 描述和选择规则，补充错选边界。",
    "Agent": "修复工具选择/参数/错误恢复并限制重复循环。",
    "Application": "根据参考答案修正最终回答，并执行 Judge 校准抽检。",
}


def build_tasks(diagnoses: list[Diagnosis]) -> list[OptimizationTask]:
    """把同组件、同根因的多条诊断合成一个可验收任务，避免重复整改。"""
    grouped: defaultdict[tuple[str, str], list[Diagnosis]] = defaultdict(list)
    for item in diagnoses:
        grouped[(item.component, item.root_cause)].append(item)
    rank = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
    tasks: list[OptimizationTask] = []
    for (component, root_cause), items in grouped.items():
        priority = min((item.severity for item in items), key=rank.get)  # type: ignore[arg-type]
        evidence = list(
            dict.fromkeys(
                [f"trace={item.trace_id}" for item in items]
                + [value for item in items for value in item.evidence]
            )
        )
        tasks.append(
            OptimizationTask(
                title=f"修复 {component}：{root_cause}",
                priority=priority,
                component=component,
                action=ACTIONS.get(component, ACTIONS["Application"]),
                evidence=evidence,
                acceptance_metric=f"{component} score >= 0.70 and no regression",
            )
        )
    return sorted(tasks, key=lambda item: (rank[item.priority], item.component, item.title))


def acceptance_gates(before: dict[str, float], after: dict[str, float]) -> dict[str, bool]:
    """闭环必须同时满足每项不回退和至少一项提升，不能只看平均分。"""
    names = sorted(before.keys() | after.keys())
    gates = {f"no_regression:{name}": after.get(name, 0) >= before.get(name, 0) for name in names}
    gates["at_least_one_improvement"] = any(
        after.get(name, 0) > before.get(name, 0) for name in names
    )
    return gates
