# 创作交接契约（game-reverse-engineering → game-creation-polish）

两个 Skill 的唯一接口是 Base 导出的 `CREATOR_HANDOFF.json`。本 Skill 不读取逆向研究的中间记录来判定 Base，也不修改它们。

## 职责划分
| 事项 | game-reverse-engineering | game-creation-polish |
|---|---|---|
| 研究原版、能力等价、表现还原 | 负责 | 只读结论 |
| Base 核心、starter、创作者工具包 | 负责（含首次使用门禁、独立复用验收） | 只使用，不修改 |
| 权利：代码与组件许可（RE01）、原版资产/表达（RE03） | 负责记录 | 发布前读取 |
| 每个游戏的策划、美术、开发、QA、发行候选 | — | 负责 |
| Base 缺陷或通用能力需求 | 接收并发布新版本 | 记录到 `core_extensions.proposed_for_base` / `retrospective.core_feedback` 回报 |

## 文件位置
`.production/bases/<base-id>/handoff/<version>/<UTC时间戳>-CREATOR_HANDOFF.json`。每次导出新建文件，不覆盖旧文件；本 Skill 读取绑定版本目录下按文件名排序的最后一份。

## 字段（schema_version = `creator-handoff-1`）
| 字段 | 含义 |
|---|---|
| `base_id`、`base_version` | 必须与游戏绑定的 Base 一致 |
| `level` | NONE / LOGIC_READY / PRESENTATION_READY / CREATOR_CANDIDATE / CREATOR_READY（由证据推导，不是自我声明） |
| `git_head`、`core_paths`、`core_fingerprint` | 导出时的提交和 Base 核心指纹 |
| `starter_paths` | 示例内容位置；游戏不得依赖或修改 |
| `fidelity.mechanism`、`fidelity.visual` | 机制保真与视觉保真分开报告 |
| `rights.RE01`、`rights.RE02`、`rights.RE03`、`rights.note` | 权利门禁状态与残余风险说明 |
| `first_use.passed`、`first_use.commit` | 干净检出首次使用门禁的结果 |
| `independent_reuse.status`、`independent_reuse.agent` | 独立 Agent 复用验收（NOT_RUN / PASS / FAIL 等） |
| `open_gaps` | 达到下一等级还缺什么（最多 20 条） |
| `files[]` | 工具包与 BASE_HANDOFF 的 `path`、`sha256`、`kit_item` |

## 本 Skill 如何使用
- `gcp.py status` 显示交接等级、两类保真度、独立复用状态和未完成项。
- 交接完整的判定：schema、Base ID/版本一致；`files[]` 中每个文件哈希不变；按 `core_paths` 重新计算的指纹等于 `core_fingerprint`。任一项不满足，等同于没有交接。
- `game create` 在交接缺失或低于 CREATOR_CANDIDATE 时仍允许开始 G1/G2 策划，但会提示；**GAME_READY 要求交接完整且 ≥ CREATOR_CANDIDATE**。
- **PUBLICATION_APPROVED 另外要求** 交接中 RE01 = PASS，RE03 = PASS 或 NOT_APPLICABLE；本游戏的 Q08、R03、R04 仍需各自 PASS。
- CREATOR_CANDIDATE 表示独立复用验收尚未通过；在这种 Base 上做游戏要在 HANDOFF 中写明“Base 尚未经过独立复用验证”，不得对外称为成熟 Base。

## Base 变化时
- 游戏不得修改 Base 核心、starter 或工具包文件；需要时回报上游。
- Base 发布新版本后：逆向 Skill 重新导出交接 → `gcp.py game rebind --id <game> --base <id>@<new>` → G5/G6 变为 NEEDS_REWORK，Q01–Q08、R01–R03 必须针对新版本重新取证。
- 交接文件或核心指纹不一致时，先确认是谁改了 Base；不要为了让校验通过而重新导出未验证的改动。

## 尚未实现（PREVIEW）
- 不自动下载或同步 Base；Base 与交接必须已在工作区中。
- 不验证交接的签名或来源，只验证字段一致与文件哈希；能写工作区的人可以伪造交接。
- 不自动把 `proposed_for_base` 转成逆向 Skill 的任务，需要人工或 Agent 转交。
