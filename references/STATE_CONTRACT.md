# 项目状态与最少记录（v4，schema 3.0）

## 位置与职责
Skill 目录存放可复用的规则；工作区、Base 和游戏的记录存放项目事实。不把项目进度写回共用 Skill 的模板，也不把模板全部拷到根目录污染原项目。

| 文件 | 作用 |
|---|---|
| `.production/WORKSPACE.json` | 研究登记、Base/游戏登记表（只存 ID 和路径）、焦点、授权范围 `run.scope`、运行模式与状态、权限、下一步 |
| `.production/BACKLOG.md` | 研究、Base 和跨游戏任务（标明受影响的游戏） |
| `.production/HANDOFF.md` | 工作区级交接：焦点、各层摘要、阻断 |
| `.production/research/<id>/` | 机制矩阵与研究笔记（受限原件不放这里，只放可以共享的摘要） |
| `.production/bases/<id>/BASE.json` | 版本列表（每个版本的就绪度和冻结状态）、能力、扩展点、资产接口、命令、限制、依赖游戏 |
| `.production/bases/<id>/GATES.json` | B01–B08，Base 门禁状态的唯一来源 |
| `games/<id>/.production/GAME.json` | brief、Base 绑定与改绑历史、G0–G7 阶段状态、就绪度、发布状态、assignment、缺陷摘要、下一步、retrospective |
| `games/<id>/.production/GATES.json` | D01–D02、Q01–Q08、R01–R04，游戏门禁状态的唯一来源 |
| `games/<id>/.production/ASSETS.json` | 资产状态（从 planned 到 verified）、运行时文件哈希、来源和许可 |
| `games/<id>/design/` | GAME_DESIGN、ART_DIRECTION、ART_ASSET_PLAN、ANIMATION_SPEC、RELEASE_CHECKLIST |
| `.production/local/ENVIRONMENT.json` | 仅本机：绝对路径、工具、版本、端口、缓存。不提交 Git，不存密钥 |

MECHANICS_MATRIX、ASSET_CONTRACT、REVIEW 和 evidence/ 按需创建，不必一次填完十几份空表。

## 枚举
- `run.mode`：auto / stage / review。`run.allowed_stages`：R0–R2、G0–G7（v3 遗留游戏可以使用 S0–S6）。
- `run.status`：NEW / RUNNING / TARGET_REACHED / HANDOFF_READY / EXTERNAL_BLOCKED / RUNTIME_LIMIT / USER_PAUSED。后三种必须写 `stop_reason`。只有授权目标的证据满足时，工具才允许记录 TARGET_REACHED。
- `run.scope.target`：research / base / game / full_pipeline / batch。`required_readiness` 默认是 RELEASE_CANDIDATE。`game_quota`：research/base 默认为 0，game/full_pipeline 默认为 1，batch 由用户指定。
- 游戏阶段状态：NOT_STARTED / IN_PROGRESS / DONE / BLOCKED / NEEDS_REWORK / NOT_APPLICABLE（必须写 stage_notes 说明依据）。
- Base 就绪度：NONE < RESEARCH_READY < BASE_READY < COMMERCIAL_BASE_CANDIDATE。
- 游戏就绪度：IN_PROGRESS < FEATURE_COMPLETE < GAME_READY < RELEASE_CANDIDATE < PUBLICATION_APPROVED。
- `publication_status`：NOT_AUTHORIZED / REVIEW_PENDING / AUTHORIZED_NOT_PUBLISHED / PUBLISHED。后两种要求游戏已达到 PUBLICATION_APPROVED。

## 就绪度如何判定
声明（`readiness` 字段）只能低于或等于证据支持的级别。工具会根据门禁推导实际级别，声明超出时报错；`update` 命令也会直接拒绝。

| 级别 | 需要（PASS，或带依据的 NOT_APPLICABLE） | 额外条件 |
|---|---|---|
| RESEARCH_READY | B01 | — |
| BASE_READY | + B03–B08 | B02 不是 FAIL；所有 PASS 的 `base_version` = 当前版本 |
| COMMERCIAL_BASE_CANDIDATE | + B02 | B02 必须是 PASS |
| FEATURE_COMPLETE | D01、Q01、Q02 | Q 门禁的 `base_version` = 游戏绑定的版本 |
| GAME_READY | + D02、Q03–Q08 | 绑定的 Base 版本 ≥ BASE_READY |
| RELEASE_CANDIDATE | + R01、R02 | 已记录产物路径与 SHA-256，并且一致 |
| PUBLICATION_APPROVED | + R03、R04 | Q08、R03、R04 必须是 PASS；R04 为 external_approval；Base 版本为 COMMERCIAL_BASE_CANDIDATE |

阶段 DONE 也会被检查：G1 需要 D01，G2 需要 D02，G5 需要 GAME_READY，G6 需要 RELEASE_CANDIDATE，G7 需要 G6 完成并写好 retrospective.summary。

## 门禁 JSON 结构
每项包含 id、name、criteria、status、scope_basis、reviewer{identity, independence}、subject_revision、base_version（B/Q/R01–R03）、evidence[]、blocker、next_action。
PASS 必须具备：具体的 criteria、subject_revision、检查者身份和真实独立性（self_review / separate_context_same_environment / independent_reviewer；external_approval 只用于 R04），以及非空 evidence。每条 evidence 包括 path（相对于该层根目录：Base 相对于工作区根，游戏相对于游戏目录）、文件 SHA-256、kind 和 observed。

## 工具职责（scripts/project.py）
| 命令 | 作用 |
|---|---|
| `init` | 按 SHA256SUMS 清单安装 Skill，创建 WORKSPACE 与工作区记录、AGENTS 引导块、本地忽略规则；不覆盖已有内容 |
| `migrate` | v3 → v4：保留全部 v3 记录字节不变，登记为遗留游戏；旧 Skill 先存档再替换 |
| `research` / `base register·bump·update` | 登记研究；登记、升级、冻结 Base；提升就绪度前核对证据 |
| `game create·stage·update·rebind` | 创建游戏并绑定 Base；阶段推进（附自动续接提示）；就绪度/发布/assignment/产物；改绑并触发回归 |
| `focus` / `scope` / `run` | 切换焦点；记录用户授权范围；记录运行状态（TARGET_REACHED 会核对证据） |
| `env` | 重新探测本机能力，只写本地文件 |
| `status` / `validate` / `handoff --check` | 只读状态；记录、证据、就绪度、隔离和路径校验；交接完整性检查 |

这些工具不运行游戏，不判断截图品质，也不做法律判断。`validate` 通过只说明记录结构正确，`--strict-target` 才会要求达到授权目标。两者都不是公开发行许可。

## 版本升级
新规则不覆盖已有的游戏数据、任务和来源记录。目标或门禁变更需要记录版本和原因；已验收的证据只在受影响的范围内失效，不能一键全绿。规则版本（kit_version）和状态 schema 分开管理。v3（schema 2.0）的记录由工具中的遗留校验器继续检查。
