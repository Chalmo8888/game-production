# 能力等价矩阵（CAPABILITY_PARITY_MATRIX）

机器记录：`.production/bases/<id>/re/PARITY.json`。人读报告：`gre.py report` 生成 `re/reports/<时间>-capability-parity.md`（每次另存，不覆盖）。

## 1. 结构
- **15 个能力域**（不能删除）：L1–L6 逻辑、P1–P8 表现、C1 扩展。
- **条目**：模板预置 38 个通用条目，可以用 `gre.py parity add` 增加游戏专有条目（ID 形如 `P2-04`）。

每个条目的字段：
| 字段 | 含义 |
|---|---|
| `original.evidence_level` / `refs` / `dynamic_gap` | 原版证据：VERIFIED / STATIC_ONLY / INFERRED / PROXY / UNKNOWN，证据文件（可标 local_research），未能动态确认的部分 |
| `approach` | REUSE / ADAPT / REIMPLEMENT / IMPROVE / OMIT / UNDECIDED |
| `reuse_modules` / `research_basis` | 复用的 KEEP/ADAPT 模块；只作研究依据的模块（可以是 QUARANTINE） |
| `status` | NOT_STARTED / RESEARCHING / INTERFACE_ONLY / DOCUMENTED / IMPLEMENTED / VERIFIED / NOT_APPLICABLE |
| `verification` / `base_version` | 验证证据（追加，不替换），验证时的 Base 版本 |
| `differences` | 与原版的重要差异和降级 |
| `reusable_for_new_games` | 能否供新游戏使用（核心条目在 Creator Ready 时必须为是） |
| `na_basis` | NOT_APPLICABLE 的依据 |
| `history` | 每次变更的记录（只追加） |

## 2. 计入完成的规则
- 只有 **VERIFIED**（当前 Base 版本、证据有效）或 **带依据的 NOT_APPLICABLE** 计入等级。
- **INTERFACE_ONLY、DOCUMENTED 不计入**：只有接口或只有文档的能力不算完成。IMPLEMENTED 也不计入，必须经过验证。
- VERIFIED 的证据必须包含 test / runtime-capture / measurement / trace / benchmark / comparison / recording 中的至少一种；表现类条目必须包含 runtime-capture / measurement / recording / comparison 中的至少一种。
- Base 升级版本后，旧版本的 VERIFIED 不再计入，需要重新验证。

## 3. 原版证据规则
- 原版 VERIFIED 需要动态证据。
- STATIC_ONLY / INFERRED / PROXY 必须写 dynamic_gap。
- UNKNOWN 不得进入 IMPLEMENTED/VERIFIED，除非 approach 为 IMPROVE 并写明独立设计说明。
- 本地研究原件（`--ref-local`）在其他设备上缺失只给出警告；共享证据缺失或被改动都是错误。

## 4. 域级规则
- 每个域都要有条目，并至少有一个 VERIFIED。L3（AI）和 L4（武器技能）可以带依据整体 N/A，其他域不行：表现、资源和音频不能整体跳过。
- 条目 N/A 的依据应来自原版证据（“原版没有这项能力”）或用户的范围（“本次 Base 不需要联机”），不能是“没有工具”。

## 5. 常用操作
```text
gre.py parity set --item L2-01 --original-level VERIFIED --original-ref research/jump.csv --ref-kind measurement
gre.py parity set --item L2-01 --approach REIMPLEMENT --research-basis orig-player
gre.py parity set --item L2-01 --evidence qa/jump-test.log --kind test --observed "apex 96px ±2 at 60fps"
gre.py parity set --item L2-01 --status VERIFIED --reusable true --differences "空中转向更灵敏（IMPROVE 记录）"
gre.py parity add --item P2-04 --domain P2 --name "武器换装挂点" --importance core
gre.py report
```

## 6. 报告怎么读
报告按 Logic / Presentation / Creator 分组，列出每个条目的原版证据等级、方式、状态、验证证据类型、重要差异和可复用性，以及 Creator 测试配置是否有效、核心指纹和权利状态（与技术等级分开）。交接和对外说明以报告和 `gre.py status` 为准，不手写结论。
