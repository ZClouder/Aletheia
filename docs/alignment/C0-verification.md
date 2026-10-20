# C0 能力矩阵与基线验证

## 结论

aletheia Python 的三阶段能力、Trace/评测/诊断/优化产物契约、实践篇模板和 C1 硬验收已
固化。返工前代码基线可运行，但不满足课程完整能力，未提前标记任何 C1–C7 项为完成。

## 审计范围

- 当前 Python 7 个源码模块、1 个测试文件、配置、Trace 和 7 类输出；
- Stage 1–3 设计文档与六篇既有实践材料的公开行为；
- 当前三篇 Python 实践提纲；
- 三阶段 CLI 和真实产物边界。

## 基线质量

| 检查 | 结果 |
|---|---:|
| Ruff lint | PASS |
| Ruff format | 8 files formatted |
| Pyright | 0 errors / 0 warnings |
| Pytest | 3 passed |

## 关键差距

1. G-Eval 没有 logprobs 概率归一化、标准步骤和受控解析；
2. 配置文件未装配，固定 Evaluation Set、Registry、EvaluationRun 均缺失；
3. RAG/Skill/Agent Evaluator 仅有单分规则骨架；
4. Stage 3 没有 LLM 归因、健康度、根因、优先级和真正的闭环 Run；
5. 三篇实践篇只有 30/34/37 行，不能用于从零复验。

完整逐项结论见 `C0-capability-matrix.md`。

## C0 验收

- [x] 三阶段公开能力逐项映射；
- [x] Trace、Case、Result、Run、Diagnosis、Task 契约明确；
- [x] 机器可读产物目录与不可覆盖原则明确；
- [x] 三篇实践篇统一模板明确；
- [x] 六道质量门明确；
- [x] C1 的 13 项硬验收明确；
- [x] 当前骨架基线重新通过自动检查。

C0 完成，自动进入 C1：Stage 1 Trace、固定测试集、PromptEvaluator、G-Eval 与报告实现。
