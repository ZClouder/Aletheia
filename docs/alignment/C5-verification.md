# C5 Stage 3 代码与闭环复验

## 结论

Stage 3 已实现规则归因、真实 LLM 归因、组件健康度、优化任务聚合、无回退门禁和产物血缘闭环。

## 自动质量门

- Ruff lint / format：PASS；
- Pyright：0 errors / 0 warnings；
- Pytest：26 passed。

## 真实诊断

源 Run：`stage2-baseline-20260808T074704-774549Z`。

Diagnosis：`diagnosis-20260808T080025-303259Z`。

- 规则诊断 13 条；
- 本地 qwen2.5 LLM 诊断 12 条；
- 健康度最低组件为 Application（0.411）；
- 规则覆盖 Prompt、Application、RAG、Skill、Agent；
- LLM 调用和结构化解析真实完成，但多数结论与规则相同，仅补充部分证据，未夸大其归因增益。

## 优化任务

Optimization：`optimization-20260808T080656-790215Z`。

规则与 LLM 诊断按 `(component, root_cause)` 合并为 6 项任务，覆盖 Application、Prompt、RAG、
Skill、Agent。每项含稳定去重的 Trace/Dimension 证据、组件动作和 `score >= 0.70 and no regression`
验收指标。

## 真实闭环

Closed loop：`closed-loop-20260808T081114-493275Z`。

血缘链：

```text
stage2-baseline-20260808T074704-774549Z
  → diagnosis-20260808T080025-303259Z
  → optimization-20260808T080656-790215Z
  → stage2-optimized-qwen2.5-20260808T074917-399779Z
```

- Before/After 评测集 SHA-256 完全一致；
- Before/After Judge 均为 qwen2.5；
- Diagnosis 的 source-run 指向 Before；
- Optimization 的 source-diagnosis 指向 Diagnosis；
- Prompt +0.250、G-Eval +0.090、RAG +0.244、Skill +0.125、Agent +0.143；
- 五项 no-regression 和 at-least-one-improvement 全部 PASS；
- `accepted=true`。

`close-loop` 没有重新评分或伪造结果，只校验并关闭此前已经真实执行的四段产物。完整 `loop` 命令的
编排路径由测试覆盖；本轮模型平台额度耗尽后没有重复消耗模型调用，避免把外部限额误写为业务失败。

## C5 验收

- [x] 规则和 LLM 两级归因；
- [x] 空诊断不调用 Judge；
- [x] 非法 JSON 一次修复；
- [x] 健康度与诊断数量分离；
- [x] 规则与 LLM 诊断共同生成任务；
- [x] 闭环比较固定评测集和 Judge；
- [x] 产物血缘不可混淆；
- [x] 无回退和提升门禁全部通过；
- [x] 真实限制如实披露。

C5 完成，自动进入 C6：Stage 3 Python 实践篇完整复验。
