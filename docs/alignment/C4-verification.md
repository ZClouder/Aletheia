# C4 Stage 2 Python 实践篇复验

## 结论

`ch09a-Python实战-Stage2.md` 已从 34 行提纲重写为完整多维评测教程，并按最终 C3 代码重新
执行 Baseline、配置 Compare 和真实多模型 Compare。

## 文档结构

| 检查 | 结果 |
|---|---:|
| 总行数 | 605 |
| 二级主章节 | 23 |
| 代码围栏 | 68，34 组配对 |
| 正文提及其他实现版本 | 0 |

教程覆盖 Stage2 Trace、五类 Evaluator、12 个新增 Dimension、Baseline/Optimized、Config/Model
两种 Compare、控制变量、产物、真实结果、自动测试、排错、故障注入、6 项练习和完整复验。

## 自动质量门

- Ruff lint / format：PASS；
- Pyright：0 errors / 0 warnings；
- Pytest：18 passed。

## 按文档真实复验

### Baseline 单次 Run

Run：`stage2-baseline-20260808T074704-774549Z`。

- 8 Cases / 40 Results；
- Successful / Failed：40 / 0；
- Prompt 0.750、G-Eval 0.411、RAG 0.756、Skill 0.875、Agent 0.857。

### 配置 Compare

Comparison：`comparison-20260808T075011-375306Z`。

- Before/After 均 40/40 成功；
- 五类 Evaluator Delta 全为正；
- Context Precision +0.5625；
- G-Eval 无 error、无降级。

### 模型 Compare

Comparison：`comparison-20260808T075201-838583Z`。

- 相同 Optimized Trace/Case；
- qwen2.5:3b 与 qwen2.5:7b 两侧均 40/40 成功；
- Prompt/RAG/Skill/Agent 以及其全部 Dimension Delta 为 0；
- G-Eval 7B-3B = -0.4973；
- 两侧 8 个 G-Eval 均真实 Logprobs、无降级。

复验结果与 C3 首轮一致，证明两类 Compare 可重复，并再次暴露 Judge 校准差异。

## C4 验收

- [x] 文档不再是提纲；
- [x] 每个 Dimension 的输入、公式、边界和证据完整；
- [x] Config/Model Compare 控制变量分别解释；
- [x] Baseline、配置对比、多模型对比全部重跑；
- [x] 每侧 Result 数、错误、降级均核对；
- [x] 负向 Judge 校准结果未隐藏；
- [x] 自动测试、真实运行和产物证据分开呈现。

C4 完成，自动进入 C5：规则归因、LLM 归因、优化任务与闭环。
