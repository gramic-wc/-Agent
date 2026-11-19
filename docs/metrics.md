# 指标记录

每次改 prompt / 检索参数 / 切块策略，跑一次 `uv run eq-eval` 并在这里追加一行。
**没有数字的优化都算猜。**

| 日期 | 改动 | cause_hit@3 | cite_coverage | card_complete | reject_acc | p95 延迟 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| — | 基线（首次跑通） | — | — | — | — | — | 填上第一行再谈优化 |

## 调参时最值得试的 5 个旋钮

1. `chunk split_text max_len`（700 → 400/1000）：颗粒度对召回影响最大
2. `RERANK_K`（30 → 15/50）与 `top_k`
3. 图纸描述 prompt（是否保留部件编号）
4. `MIN_CONFIDENCE`（0.35）：调高 → 转人工变多、错判变少
5. `MAX_TRIES`（1 → 2）：自检重判次数与延迟的权衡

## 已知失败模式（填进这里，别只在脑子里记）

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 型号不明的描述召回乱 | 未做设备型号过滤 | retrieve 前先 identify |
| 图表类问题答不出 | 图纸未做 VLM 描述 / 图注未关联 | 检查 `figure_no` 与 caption 距离阈值 |
| 引用指向不相关页 | rerank 关掉了或 chunk 太长 | 打开 rerank、缩短 chunk |
| 每次结论都不一样 | temperature 与 prompt 不稳定 | diagnose/plan 用 0.1~0.2 |
