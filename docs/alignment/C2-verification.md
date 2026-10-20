# C2 Stage 1 Python 实践篇复验

## 结论

`ch06a-Python实战-Stage1.md` 已从 30 行提纲重写为可从环境准备执行到独立 Run 报告的完整
教程，并按最终 C1 代码从 `record` 开始重新执行。

## 文档结构

| 检查 | 结果 |
|---|---:|
| 总行数 | 662 |
| 二级主章节 | 23 |
| 代码围栏 | 78，39 组配对 |
| 正文提及其他实现版本 | 0 |
| 引用工程文件 | 全部存在 |

教程覆盖严格契约、固定 Sample、JSONL、Prompt 四维、G-Eval 两步协议、Logprobs 概率期望、
Registry、有界并发、局部失败、汇总、不可覆盖 Run、自动测试、排错、故障注入、6 项练习和完整
复验清单。

## 按文档复验

### 自动质量门

- Ruff lint：PASS；
- Ruff format：11 files formatted；
- Pyright：0 errors / 0 warnings；
- Pytest：11 passed。

### 输入

- `recorded=8`；
- status：8 Traces / 8 Cases；
- `data/traces.jsonl`：8 行；
- model/judge：qwen2.5；
- max_concurrency：4。

### 真实 Run

复验 Run：`run-20260808T072958-721327Z`。

| 项目 | 结果 |
|---|---:|
| Results | 16 |
| Successful / Failed | 16 / 0 |
| G-Eval | 8 |
| G-Eval degraded | 0 |
| Result errors | 0 |
| Prompt mean | 0.7500 |
| G-Eval mean | 0.3922 |

该 Run 与 C1 最终 Run 的聚合值一致，证明 temperature=0 和固定输入下本轮结果可重复。Run 目录
包含 manifest、Trace 快照、逐条结果、汇总和 Markdown 五个文件。

## 环境说明

正式工程不提交 `.venv`，当前桌面 shell 的 uv 也不在 PATH。代码复验使用由同一 `uv.lock` 已
创建的 Python 3.11 环境；实践篇明确要求学习者先安装 uv 并执行 `uv sync --frozen`，不把临时
虚拟环境复制进正式交付。

## C2 验收

- [x] 文档不再是提纲或命令清单；
- [x] 所有代码、文件名和命令对应最终 C1 实现；
- [x] 规则分数、模型分数和真实性边界分开解释；
- [x] 真实 Run 从 record/status 开始重新执行；
- [x] 16 条结果、8 个 Logprobs G-Eval 全部成功；
- [x] 自动质量门和 Run 产物均有证据；
- [x] 故障注入、练习和验收清单完整。

C2 完成，自动进入 C3：Stage 2 RAG、Skill、Agent Evaluator、Registry/Pipeline 与多配置对比。
