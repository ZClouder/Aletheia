# Aletheia（Python）

Aletheia 是一个围绕 AI 应用 Trace 建立“评测 → 诊断 → 优化 → 复测”闭环的三阶段教学项目。
Python 实现采用原生异步架构、Pydantic 数据契约和显式 CLI，不依赖大型 Agent/RAG 框架。

## 三阶段

| Stage | 核心能力 | 实践文档 |
|---|---|---|
| 1 | Trace/Case、Prompt 四维、G-Eval Logprobs、独立 Run | `ch06a-Python实战-Stage1.md` |
| 2 | RAG/Skill/Agent、Registry、配置/模型对比 | `ch09a-Python实战-Stage2.md` |
| 3 | 规则/LLM 归因、优化任务、血缘闭环、回退门禁 | `ch12a-Python实战-Stage3.md` |

## 环境

- Python 3.11+
- uv
- Ollama OpenAI 兼容端点 `http://localhost:11434/v1`
- Judge 模型 `qwen2.5`（模型名可在 `config/local.yaml` 修改）

```bash
uv sync
ollama list
uv run aletheia status
```

## 快速开始

### Stage 1：基础评测

```bash
uv run aletheia record --profile baseline
uv run aletheia status
uv run aletheia eval 1
```

### Stage 2：多维评测与对比

```bash
uv run aletheia eval 2
uv run aletheia compare --mode config
uv run aletheia compare --mode model \
  --before-model qwen2.5:3b --after-model qwen2.5:7b
```

配置对比使用 Baseline/Optimized Trace；模型对比固定 Optimized Trace，只改变 Judge。

### Stage 3：诊断与优化

```bash
uv run aletheia diagnose --run-id <run-id>
uv run aletheia optimize --diagnosis-id <diagnosis-id>
uv run aletheia loop
```

跨提交执行优化时，可以关闭四段已有真实产物：

```bash
uv run aletheia close-loop \
  --before-run <baseline-run-id> \
  --diagnosis-id <diagnosis-id> \
  --optimization-id <optimization-id> \
  --after-run <optimized-run-id>
```

`close-loop` 会校验评测集 SHA-256、Judge 模型、Diagnosis 来源和 Optimization 来源，然后计算
每类 Evaluator 的无回退门禁。

## 目录

```text
Aletheia/
├── config/local.yaml
├── data/
│   ├── traces.jsonl
│   └── eval_set.json
├── src/aletheia/
│   ├── models.py
│   ├── config.py
│   ├── storage.py
│   ├── sample_app.py
│   ├── judge.py
│   ├── evaluators.py
│   ├── engine.py
│   ├── diagnosis.py
│   ├── optimization.py
│   ├── reporting.py
│   └── cli.py
├── tests/
└── output/
```

## 产物契约

每次评测写入不可覆盖的 Run 目录：

```text
output/<run-id>/
├── manifest.json
├── traces.jsonl
├── evaluation-results.json
├── evaluation-summary.json
└── evaluation-report.md
```

诊断、优化和闭环也分别创建时间戳目录，并通过 `source-run.txt`、`source-diagnosis.txt` 和
`loop.json` 保存血缘。JSON 是机器输入，Markdown 是阅读视图。

## 评测维度

| Evaluator | Dimension |
|---|---|
| Prompt | role、task、constraint、format |
| G-Eval | overall、task_completion、answer_relevancy |
| RAG | faithfulness、context_precision、context_recall、answer_relevancy、citation_correctness |
| Skill | skill_selection、skill_match |
| Agent | tool_selection、tool_arguments、tool_success、agent_efficiency、task_completion |

## 质量检查

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```

当前基线：Ruff lint/format 通过、Pyright 0 errors、Pytest 26 passed。

## 设计边界

- 主运行链路真实调用 Ollama，不提供面向用户的 mock/local 模式；
- 单元测试通过依赖注入验证纯逻辑，不替代真实模型验证；
- Stage 3 的 LLM 归因是规则增强，模型输出必须通过严格 JSON/Pydantic 校验；
- 模型对比用于校准 Judge，不可直接当作应用优化结论；
- 闭环必须固定评测集与 Judge，且所有既有 Evaluator 无回退。

完整学习路径从 `docs/aletheia/ch00-学习指引.md` 开始。
