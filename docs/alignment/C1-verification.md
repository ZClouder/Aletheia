# C1 Stage 1 Trace、Prompt 与 G-Eval 验证

## 结论

Stage 1 已从单条内置 Sample 骨架重建为严格配置、固定 8 案例、Prompt 四维规则评测、真实
qwen2.5 G-Eval、logprobs 概率归一化、有界并发、局部失败和不可覆盖 Evaluation Run 产物。

## 自动质量门

| 检查 | 结果 |
|---|---:|
| Ruff lint | PASS |
| Ruff format | 11 files formatted |
| Pyright | 0 errors / 0 warnings |
| Pytest | 11 passed |

测试覆盖严格 Trace/Span/Config、重复 Span/Trace/Case ID、坏 JSONL 行号、Prompt 四维、无 Prompt
Span、Judge JSON 修复、logprobs 期望分、无 logprobs 降级、Registry、有界并发、局部失败、
稳定顺序、Summary 和 Run 目录不可覆盖。

## 固定数据与协议

- 8 个稳定 Trace ID 和 8 个 Evaluation Case ID；
- 正样本、缺角色/任务/约束/格式、无关回答、不完整回答、缺 Prompt Span；
- Evaluation Set SHA256：`430937f860ab0ff75c142baa03f6595597063758ce7879c56a6601228c4e111a`；
- PromptEvaluator 输出 role/task/constraint/format 四个 Dimension；
- G-Eval 先生成具体分析 JSON，再单独输出 1–5 分并对 Top Logprobs 做概率期望。

## 真实 Ollama Run

最终有效 Run：`run-20260808T071827-366493Z`。

| 项目 | 结果 |
|---|---:|
| Cases | 8 |
| Evaluation Results | 16 |
| Successful / Failed | 16 / 0 |
| Prompt mean | 0.7500 |
| G-Eval mean | 0.3922 |
| G-Eval degraded | 0 / 8 |

G-Eval 对三类答案形成明显区分：覆盖三点的简短回答约 0.47–0.48，单点不完整回答 0.278，
无关回答 0.0016。qwen2.5 仍认为三点回答缺少执行细节；该判断保留为真实 Judge 结果，没有手调
分数。总 `pass_rate` 按结果是否超过 0.70 计算，包含刻意设计的负样本，因此不能解释成评测器
分类准确率。

## Run 产物

每次评测生成独立目录，本次包含：

- `manifest.json`：阶段、时间、模型、配置、数据哈希、成功/失败；
- `traces.jsonl`：本次只读输入快照；
- `evaluation-results.json`：449 行逐结果、维度、理由、证据、原始 Judge；
- `evaluation-summary.json`：Evaluator/Dimension 聚合；
- `evaluation-report.md`：46 行人工阅读报告。

再次使用同一个 Run ID 写入会抛出 `FileExistsError`，不会覆盖 Baseline。

## 真实运行发现并修正

1. 初版分析 JSON 给了固定示例值“简洁分析”，模型照抄：移除示例值，改为字段类型协议；
2. Judge 对简短正确答案要求参考之外的展开：明确参考答案是完整性边界；模型仍认为执行细节
   不足，作为模型校准现象保留；
3. 旧 Pipeline 无界 gather 且一个异常中止整批：改为 Semaphore + 每结果错误隔离；
4. 旧 CLI 未读取 YAML：全部入口先通过严格 AppConfig 装配。

## C1 验收

- [x] 严格 Config 与 Trace/Span/Case/Result/Run；
- [x] JSONL 往返、坏行定位、重复 ID；
- [x] 8 条固定 Case 与稳定 Sample Trace；
- [x] Evaluator Protocol 与 Registry；
- [x] Prompt 四维规则结果；
- [x] G-Eval 标准、分析、评分两步协议；
- [x] logprobs 概率归一化与降级路径；
- [x] 有界并发、顺序和局部失败；
- [x] 独立 Run manifest、JSON、Markdown；
- [x] record/eval 1/status CLI；
- [x] 自动质量门和真实 qwen2.5 Run。

C1 完成，自动进入 C2：将 Stage 1 Python 实践篇重写为完整教程并按文档复验。
