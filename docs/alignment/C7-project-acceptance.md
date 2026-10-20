# C7 aletheia Python 项目级验收

## 范围

项目级验收覆盖 Stage 1–3 的代码、自动质量门、真实运行产物、README 和三篇 Python 实践文档。

## 自动回归

| 门禁 | 结果 |
|---|---:|
| Ruff lint | PASS |
| Ruff format | PASS（51 files） |
| Pyright | 0 errors / 0 warnings |
| Pytest | 26 passed |

## 阶段能力

### Stage 1

- 严格 Trace/Span/Case/Result/Run 契约；
- Prompt 四维和 G-Eval 两步协议；
- Logprobs 概率期望与显式降级字段；
- 真实 Run 16/16 Result 成功、8 个 G-Eval 均使用 Logprobs。

### Stage 2

- RAG 五维、Skill 两维、Agent 五维；
- Registry、有界并发、Result 级错误隔离；
- 配置对比五类 Evaluator 全提升；
- 多模型对比固定输入并暴露 Judge 校准差异。

### Stage 3

- 规则归因与真实 qwen2.5 结构化归因；
- 组件健康度和 6 项证据化优化任务；
- 固定评测集、固定 Judge、四段血缘闭环；
- 五个无回退 Gate 与至少一项提升 Gate 全 PASS。

## 真实证据索引

| 证据 | ID |
|---|---|
| Stage 1 最终 Run | `run-20260808T072958-721327Z` |
| Stage 2 Baseline | `stage2-baseline-20260808T074704-774549Z` |
| Stage 2 Config Compare | `comparison-20260808T075011-375306Z` |
| Stage 2 Model Compare | `comparison-20260808T075201-838583Z` |
| Stage 3 Diagnosis | `diagnosis-20260808T080025-303259Z` |
| Stage 3 Optimization | `optimization-20260808T080656-790215Z` |
| Stage 3 Closed Loop | `closed-loop-20260808T081114-493275Z` |

## 文档验收

| 实践篇 | 行数 | H2 | 围栏 |
|---|---:|---:|---:|
| Stage 1 | 662 | 23 | 78 |
| Stage 2 | 605 | 23 | 68 |
| Stage 3 | 753 | 23 | 74 |

三篇均覆盖环境、运行、核心实现、真实结果、异常排查、练习与验收，不再是提纲。正文保持 Python
实现的独立叙事。

## 已知边界

- 本轮末尾模型平台额度限制阻止再次重复执行完整 `loop`，但其组成步骤此前均真实运行，新增
  `close-loop` 已严格验证并关闭同一真实产物链；
- LLM 归因多数复述规则结果，只能证明真实通路与协议成立，不能宣称已超过规则准确率；
- 当前门禁基于均值，生产扩展应增加样本级显著性、成本和延迟门禁。

## 结论

aletheia Python 的 Stage 1–3 主链路、三篇实践文档和可追溯验证证据齐备，C0–C7 项目阶段验收通过。
