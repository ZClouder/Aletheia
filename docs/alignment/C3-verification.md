# C3 Stage 2 RAG、Skill、Agent 与对比验证

## 结论

Stage 2 已在统一 Registry/Pipeline 中加入 RAG、Skill、Agent Evaluator，并完成同模型配置对比和
同输入多模型对比。每条 Stage2 Case 执行 Prompt、G-Eval、RAG、Skill、Agent 五类评测，共
40 条 Result；Baseline、Optimized 和 Comparison 均使用独立目录。

## 自动质量门

| 检查 | 结果 |
|---|---:|
| Ruff lint / format | PASS |
| Pyright | 0 errors / 0 warnings |
| Pytest | 18 passed |

新增测试覆盖 RAG 五维与缺 Retrieval、Skill 错选/修复、Tool 参数、工具错误、重复调用、超轮次、
Stage 路由、Summary Delta，以及 config/model 两种 compare CLI。

## 评测维度

### RAG

- Faithfulness；
- Answer Relevancy；
- Context Precision；
- Context Recall；
- Citation Correctness。

### Skill

- Skill Selection；
- Skill Match。

### Agent

- Tool Selection；
- Tool Arguments；
- Tool Success；
- Agent Efficiency；
- Task Completion。

## 同模型配置对比

固定 qwen2.5、固定 8 Case，Baseline 包含 Prompt 缺项、噪声 Context、Skill 错选、参数错误、
工具失败、重复工具/超轮次、错误引用和不完整回答；Optimized 修正上述 Trace。

| Evaluator | Baseline | Optimized | Delta |
|---|---:|---:|---:|
| prompt | 0.750 | 1.000 | +0.250 |
| g-eval | 0.411 | 0.502 | +0.090 |
| rag | 0.756 | 1.000 | +0.244 |
| skill | 0.875 | 1.000 | +0.125 |
| agent | 0.857 | 1.000 | +0.143 |

两个 Run 均 40/40 Result 成功，G-Eval 无降级。Comparison：
`comparison-20260808T073742-998348Z`。

## 真实多模型对比

本机已安装 `qwen2.5:3b` 与 `qwen2.5:7b`。模型模式对两者使用完全相同的 Optimized Trace、Case、
规则评测和参数，只改变 Judge model：

| Evaluator | 3B | 7B | Delta（7B-3B） |
|---|---:|---:|---:|
| prompt | 1.000 | 1.000 | 0.000 |
| rag | 1.000 | 1.000 | 0.000 |
| skill | 1.000 | 1.000 | 0.000 |
| agent | 1.000 | 1.000 | 0.000 |
| g-eval | 0.999 | 0.502 | -0.497 |

两个模型的 8 个 G-Eval 均使用真实 Logprobs、无降级、无错误。3B 对与参考答案一致的回答几乎
全部给 5 分，而 7B 稳定给约 3 分，暴露显著 Judge 校准差异。不能由该结果推导“3B 应用质量
更好”；它证明更换 Judge 模型会改变评分尺度，跨模型报告必须先校准。

Comparison：`comparison-20260808T074159-772225Z`。

## 产物隔离

- 配置对比：两个 Stage2 Run + 一个 Comparison；
- 模型对比：两个 Stage2 Run + 一个 Comparison；
- 每个 Run 保留 Manifest 中的 profile、Judge model、数据哈希和完整配置；
- Comparison JSON 保存 before/after Summary、Run ID、mode 和全部 Delta。

## C3 验收

- [x] RAG 五维结果与缺 Retrieval 边界；
- [x] Skill 选择/匹配；
- [x] Agent 工具选择、参数、成功、效率、完成度；
- [x] Stage1 Case 不被 Stage2 路由原地修改；
- [x] Baseline/Optimized 同配置对比；
- [x] qwen2.5:3b / qwen2.5:7b 同输入真实对比；
- [x] 规则维度在模型对比中保持零 Delta；
- [x] 所有 Run/Comparison 可追溯且不可覆盖；
- [x] 自动质量门和真实 Ollama 全通过。

C3 完成，自动进入 C4：Stage2 Python 实践篇与固定数据集复验。
