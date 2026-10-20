# 能力等价矩阵（CAPABILITY_PARITY_MATRIX）

机器记录：`.production/bases/<id>/re/PARITY.json`。人读报告：`gre.py report` 生成 `re/reports/<时间>-capability-parity.md`（每次另存，不覆盖）。

## 1. 结构
- **15 个能力域**（不能删除）：L1–L6 逻辑、P1–P8 表现、C1 扩展。
- **通用条目**：模板预置 38 个（`origin: template`）。它们只是起始检查清单，不是能力上限。
- **游戏特有条目**：从原版代码、运行行为和资源结构中发现的独特机制（`origin: discovered`，ID 形如 `L5-04`），用 `gre.py parity add --source code|runtime|assets --evidence <发现位置>` 加入。
- **原创扩展条目**：为今后创作新增的通用能力（`origin: extension`，类别固定为 EXTENSION）。
- **表现系统重建**：P 域条目说明 Base“有什么表现能力”；原作“怎样把资源、坐标、动画、渲染、UI 与玩法状态组合成画面”的调查（PR01–PR13，每项带 A/B/C/D 判定）、帧研究和场景实验（PX01–PX09）记录在 `re/PRESENTATION.json` 中，每个调查项都链接到相关的 P 条目，门禁规则见 [PRESENTATION_2D 第 5 节](PRESENTATION_2D.md)。调查项判定为 C/D 或 Base 方法与原版不同时，关联条目不能声称 PARITY；调查结论被更正后，关联条目的验证自动过期。
- **发现记录**：`discovery.sources.code / runtime / assets` 的状态为 PENDING / DONE / UNAVAILABLE（必须写原因），并附审查证据和发现的条目（`gre.py discover`）。三类来源都完成或注明无法获得，才能达到 LOGIC_READY。

## 2. 条目字段
| 字段 | 含义 |
|---|---|
| `scope` / `scope_reason` | core（必须完成）/ optional（可选）/ legacy（只为历史兼容）/ excluded（明确排除）。模板条目降级或任何排除都要写理由 |
| `origin` / `discovery` | template / discovered / extension；discovered 条目必须附发现位置的证据 |
| `capability_class` | PARITY / REPLACEMENT / EXTENSION（见第 3 节） |
| `original.evidence_level` / `refs` / `dynamic_gap` | 原版证据：VERIFIED / STATIC_ONLY / INFERRED / PROXY / UNKNOWN，证据文件（可标本地研究），未能动态确认的部分 |
| `approach` | REUSE / ADAPT / REIMPLEMENT / IMPROVE / OMIT / UNDECIDED |
| `reuse_modules` / `research_basis` | 复用的 KEEP/ADAPT 模块；只作研究依据的模块（可以是 QUARANTINE） |
| `code_paths` | 本能力相关的代码目录（默认是全部 core_paths），用于代码指纹绑定 |
| `value` | impact（1–3）和 cost（S/M/L），供 `gre.py next` 排序 |
| `status` | NOT_STARTED / RESEARCHING / INTERFACE_ONLY / DOCUMENTED / IMPLEMENTED / VERIFIED / NOT_APPLICABLE |
| `verification` / `base_version` / `verified_fingerprint` | 验证证据（追加，不替换）、验证时的 Base 版本和相关代码指纹 |
| `differences` / `design_note` | 与原版的重要差异和降级；原创设计说明 |
| `reusable_for_new_games` | 能否供新游戏使用（core 条目在 Creator Ready 时必须为是） |
| `history` | 每次变更的记录（只追加） |

## 3. 能力来源：PARITY、REPLACEMENT、EXTENSION
| 类别 | 含义 | 必要条件 |
|---|---|---|
| PARITY | 有原版证据支持的等价能力 | 原版证据为 VERIFIED，或 STATIC_ONLY 并写明 dynamic_gap |
| REPLACEMENT | 用不同的合规实现提供对应能力（例如成熟开源组件替代原作曲线） | 原版能力存在（证据等级不是 UNKNOWN）；写明 differences |
| EXTENSION | 为今后创作新增的原创能力 | 写明 design_note；原版行为可以是 UNKNOWN |

- 原版行为尚不明确（INFERRED / PROXY / UNKNOWN）时不得宣称 PARITY。
- UNKNOWN 的能力只有**显式**标为 EXTENSION 才能实现。
- 报告和状态分别统计三类的数量，EXTENSION 会标注“原创扩展，不是逆向成果”。
- 1.0.0 留下的旧记录没有类别时，会按保守规则推导（UNKNOWN → EXTENSION，INFERRED/PROXY → REPLACEMENT，VERIFIED/STATIC_ONLY → PARITY），并提示补充显式类别。

## 4. 计入完成的规则
- 只有满足以下条件的条目计入等级：scope 为 core，且状态为 VERIFIED（当前 Base 版本、相关代码指纹未变、证据有效），或带依据的 NOT_APPLICABLE。optional、legacy 不阻断等级，excluded 只需要写明理由。
- **INTERFACE_ONLY、DOCUMENTED 不计入**，IMPLEMENTED 也必须经过验证。
- VERIFIED 的证据必须包含 test / runtime-capture / measurement / trace / benchmark / comparison / recording 中的至少一种；表现类条目必须包含 runtime-capture / measurement / recording / comparison 中的至少一种。
- **代码改动后旧 QA 失效**：验证时记录 `code_paths`（默认全部 core_paths）的指纹，这些文件一旦改变，条目就显示为“过期”并不再计入，需要重新验证。改动无关目录不会影响用 `code_paths` 限定过的条目。
- Base 升级版本后，旧版本的 VERIFIED 也不再计入。

## 5. 域级规则
- 每个域都要有条目，并至少有一个 VERIFIED。L3（AI）和 L4（武器技能）可以带依据整体 N/A，其他域不行：表现、资源和音频不能整体跳过，也不能整体排除。
- N/A 或排除的依据应来自原版证据（“原版没有这项能力”）或用户的范围（“本次 Base 不需要联机”），不能是“没有工具”或“太难”。

## 6. 常用操作
```text
gre.py discover --source code --status DONE --evidence research/code-review.md --findings L5-04
gre.py parity add --item L5-04 --domain L5 --name "时间回溯关卡机制" --source code --evidence research-private/rewind.txt --ref-local
gre.py parity set --item L2-01 --original-level VERIFIED --original-ref research/jump.csv --ref-kind measurement
gre.py parity set --item L2-01 --class PARITY --approach REIMPLEMENT --code-paths engine/core/physics
gre.py parity set --item L2-01 --evidence qa/jump-test.log --kind test --observed "apex 96px ±2 at 60fps" --status VERIFIED --reusable true
gre.py parity set --item L4-01 --class EXTENSION --design-note "原版武器表未知，独立设计的数据驱动武器 schema"
gre.py parity set --item L6-02 --scope excluded --scope-reason "原版在线排行榜，不在离线 Base 范围内"
gre.py report
```

## 7. 报告怎么读
报告按 Logic / Presentation / Creator 分组，列出每个条目的范围、来源（模板/发现/扩展）、原版证据等级、类别、方式、状态（含“过期”）、验证证据类型、重要差异和可复用性，以及 Creator 测试配置、核心指纹、按价值排序的下一步和权利状态（与技术等级分开）。交接和对外说明以报告和 `gre.py status` 为准，不手写结论。
