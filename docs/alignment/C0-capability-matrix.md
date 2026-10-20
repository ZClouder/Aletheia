# C0 aletheia Python 三阶段能力矩阵

## 1. 审计目的

本矩阵用于约束 aletheia Python 的返工范围。完成状态只按当前 Python 代码、自动测试、真实
Ollama 运行和可复验产物判断；其他实现仅用于识别课程公开能力，不作为 Python 文档叙事主体。

返工前基线：

- Python 源码 414 行，测试 30 行 / 3 项；
- Stage 1/2/3 实践篇分别 30、34、37 行；
- 数据目录只有 1 条手写 Trace，没有固定 Evaluation Set；
- 7 类输出文件可生成，但多数来自单条内置 Sample 和规则骨架；
- Ruff、format、Pyright 和 3 项 Pytest 通过。

因此当前状态是“命令骨架可运行”，不是三阶段课程能力完成。

## 2. 统一领域契约

| 对象 | 必要字段 | 约束 | 当前状态 | 目标 |
|---|---|---|---|---|
| Trace | id/query/response/model/spans/metadata | ID 唯一、必填非空、可 JSONL 往返 | 弱类型 dataclass，无校验 | Pydantic 严格契约 |
| Span | id/name/kind/input/output/timing/attributes | kind 枚举、耗时非负、错误可观察 | 无 id，kind 任意字符串 | 强类型 SpanKind |
| EvaluationCase | id/query/expected/reference/metadata | 固定集、ID 唯一、可加载校验 | 缺失 | Stage1 建立 |
| EvaluationResult | trace/case/evaluator/dimension/score/reason/evidence | score 0–1，记录 Judge 原始信息 | 只有基础字段 | 完整结果契约 |
| EvaluationRun | run_id/stage/config/model/results/summary | 同批输入、环境可追溯 | 缺失 | 三阶段统一产物 |
| Diagnosis | trace/component/severity/root_cause/evidence | 规则与 LLM 归因可区分 | 简单阈值映射 | Stage3 完整 |
| OptimizationTask | priority/component/action/evidence/acceptance | 可执行、可验收、可追踪来源 | 缺 priority/root cause | Stage3 完整 |

真实性边界：纯逻辑测试可用 Fake Judge；课程主链路必须调用真实 Ollama。不得把静态 Sample 的
规则分数描述为真实 LLM-as-Judge 结果。

## 3. Stage 1：Trace、Prompt 与 G-Eval

| 能力 | 课程行为 | 当前实现 | 差距 | 验收证据 |
|---|---|---|---|---|
| 严格配置 | YAML 加载 LLM/Judge/路径/阈值 | CLI 常量，配置未读取 | 高 | 非法字段/阈值测试 |
| Trace Record | 被测应用写完整 Span | 单个内置 sample | 高 | 固定 Sample App 多案例 |
| JSONL Store | append/read/坏行定位/重复 ID | 基础 append/read | 中 | 往返、坏 JSON、重复测试 |
| Evaluation Set | 固定 Case 与期望 | 缺失 | 高 | 至少 8 条固定集 |
| Evaluator Protocol | 统一异步接口 | `object` + type ignore | 高 | Protocol/Registry 测试 |
| Registry | 注册、列出、选择、未知名失败 | 缺失 | 高 | 独立测试 |
| Prompt 规则评测 | 角色/任务/约束/格式与证据 | 三项关键词 | 中 | 多边界、维度明细 |
| G-Eval 步骤 | 标准、步骤、评分三段 Prompt | 单句 Prompt | 高 | Prompt 快照测试 |
| JSON 解析 | Fence/前后文字/重试/错误 | 直接 `json.loads` | 高 | 坏响应测试 |
| logprobs | 候选分数概率归一化 | 缺失 | 高 | 数学单测 + 真实响应 |
| G-Eval 结果 | score/reason/steps/evidence/raw | score/reason | 高 | 完整 JSON 报告 |
| Pipeline | Trace × Evaluator，有界并发、局部失败 | 无界 gather、失败整体中止 | 高 | 顺序/并发/局部失败 |
| 汇总 | 维度均值、逐条明细、通过率 | 只有逐条表 | 高 | JSON + Markdown |
| CLI | record/eval 1/status | record/eval | 中 | 逐命令真实运行 |

### Stage 1 固定数据

至少覆盖：

1. Prompt 完整、回答正确；
2. 缺少角色；
3. 缺少任务；
4. 缺少约束；
5. 缺少输出格式；
6. 回答不相关；
7. 回答不完整；
8. Trace 缺 Prompt Span。

每个 Case 必须有稳定 ID、输入、参考答案和应启用的 Evaluator，不能运行时随机生成 UUID 后再
声称是固定基线。

## 4. Stage 2：RAG、Skill、Agent 与对比

| 能力 | 课程行为 | 当前实现 | 差距 | 验收证据 |
|---|---|---|---|---|
| RAG Faithfulness | 回答声明是否受 Context 支持 | 词项覆盖率单分 | 高 | 声明级 Judge |
| RAG Relevancy | 回答是否切题 | 缺失 | 高 | 独立维度 |
| Context Precision | 相关文档排序质量 | 缺失 | 高 | 排名 Case |
| Context Recall | 参考事实召回覆盖 | 缺失 | 高 | 固定 relevant IDs |
| Citation | 引用是否属于 Context | 缺失 | 高 | 正/误引用 |
| Skill Selection | 是否选中正确 Skill | 只判断 matched=true | 高 | expected_skill |
| Skill Args/Output | 参数与结果是否满足任务 | 缺失 | 高 | 边界 Case |
| Agent Tool Selection | 工具是否正确 | 只统计 error | 高 | expected_tools |
| Agent Arguments | 工具参数是否正确 | 缺失 | 高 | 参数断言 |
| Agent Task Completion | 最终任务是否完成 | 缺失 | 高 | Judge/规则组合 |
| Agent Efficiency | 循环、重复工具、失败恢复 | 仅 iterations > 5 扣分 | 中 | 多边界测试 |
| Evaluator Registry | prompt/rag/skill/agent/g-eval | 缺失 | 高 | 选择与组合 |
| Pipeline | 按 Case 路由 Evaluator | 全 Trace 跑全部 Evaluator | 高 | 适用性测试 |
| 模型/配置对比 | 相同固定集 before/after 或模型 A/B | 仅比较两个内置 Prompt | 高 | Run manifest + delta |
| 汇总 | 按 Evaluator/维度/Case/模型 | 简单均值 delta | 高 | JSON + Markdown |
| CLI | eval 2/compare/status | 骨架存在 | 中 | 真实报告 |

Stage 2 不要求接入真实业务 RAG/Agent 服务，但 Trace 必须足以还原检索、Skill 与 Tool 行为；
Sample App 至少生成正确、错误选择、错误参数、工具失败、超轮次和知识不足等案例。

## 5. Stage 3：诊断、归因与优化闭环

| 能力 | 课程行为 | 当前实现 | 差距 | 验收证据 |
|---|---|---|---|---|
| 规则归因 | 按指标映射 Prompt/RAG/Skill/Agent | 基础映射 | 中 | 阈值边界测试 |
| 严重度 | score + 影响面确定 high/medium/low | 仅两个等级 | 高 | 三等级测试 |
| Root Cause | 明确失败机制，不只重复 reason | 缺失 | 高 | 结构化 Diagnosis |
| LLM 归因 | 综合 Trace/Result 生成结构化归因 | 缺失 | 高 | 真实 Ollama + 降级 |
| JSON 提取 | Fence/杂文/重试/Schema | 缺失 | 高 | 解析测试 |
| 健康度 | 总体及组件健康 | 缺失 | 高 | diagnosis JSON/MD |
| 瓶颈排序 | 按严重度与分数稳定排序 | 缺失 | 高 | 稳定顺序测试 |
| Level 1 报告 | 健康度、瓶颈、证据、根因 | 列表四行 | 高 | 完整报告 |
| Level 2 Task | 优先级、动作、证据、验收指标 | 简单模板 | 高 | 可执行任务文档 |
| 去重合并 | 相同根因跨 Trace 合并 | 缺失 | 高 | 聚合测试 |
| 优化执行 | 生成优化配置/Prompt，不直接篡改基线 | 只生成任务 | 高 | before/after 产物 |
| 闭环 | baseline → diagnose → optimize → rerun → compare | 两个静态 sample | 高 | 独立 Run ID |
| 防回归 | 改善目标维度且其他维度不越界 | 缺失 | 高 | acceptance gate |
| CLI | diagnose/optimize/loop/status | 骨架存在 | 中 | 全部产物真实生成 |

## 6. 产物契约

每次执行使用独立 `run_id` 目录，最低产物如下：

```text
output/<run_id>/
├── manifest.json
├── traces.jsonl
├── evaluation-results.json
├── evaluation-report.md
├── diagnosis.json
├── diagnosis.md
├── optimization-tasks.json
├── optimization-tasks.md
└── comparison.json
```

`manifest.json` 至少记录：stage、开始/结束时间、模型、配置摘要、Evaluation Set 哈希、Trace 数、
Evaluator 列表、成功/失败数量。报告不得只有 Markdown；机器可读 JSON 是后续归因和闭环输入。

原始 Trace 与 Evaluation Set 只读。优化后必须生成新 Run，不能覆盖 baseline 后再计算“提升”。

## 7. 三篇实践文档模板

每篇至少包含：

1. 本章目标与阶段新增能力；
2. 环境、配置和工程结构；
3. 领域契约与数据准备；
4. 核心实现逐段走读；
5. CLI 完整命令；
6. 固定案例和预期产物；
7. 真实 Ollama 关键输出；
8. 指标解释和真实性边界；
9. 常见问题与故障注入；
10. 至少 4 项动手练习；
11. 从空 output 开始的完整复验；
12. 验收清单。

禁止只列类名、命令和练习；代码摘录必须解释输入、输出、异常和为什么这样设计。

## 8. 六道质量门

每个 C 阶段必须依次通过：

1. 能力矩阵对应项已实现；
2. Ruff lint + format、Pyright、Pytest；
3. 真实 Ollama 主链路；
4. 固定数据集与机器可读产物；
5. 完整 Python 实践篇；
6. 按实践篇从空产物目录复验。

## 9. C1 硬验收清单

- [ ] Pydantic 严格配置与 Trace/Span/Case/Result/Run 契约；
- [ ] JSONL Store 往返、坏行定位和重复 ID；
- [ ] 至少 8 条固定 Evaluation Case；
- [ ] Sample App 生成稳定 Trace，不依赖随机 ID 建 Baseline；
- [ ] Evaluator Protocol 与 Registry；
- [ ] Prompt 规则维度明细；
- [ ] G-Eval 标准/步骤/评分 Prompt；
- [ ] logprobs 候选分数概率归一化；
- [ ] Judge JSON 受控解析、重试和明确失败；
- [ ] 有界并发、稳定顺序与局部失败；
- [ ] EvaluationRun manifest、JSON 与 Markdown 汇总；
- [ ] record/eval 1/status CLI；
- [ ] 自动质量门和真实 qwen2.5 评测全部通过。

C0 完成后只进入 C1，不提前扩写实践篇。C2 必须以 C1 最终代码和真实报告为准。
