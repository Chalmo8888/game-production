# Base 与多游戏模型

## 三个层次
| 层次 | 位置 | 记录什么 |
|---|---|---|
| Workspace | `.production/WORKSPACE.json`、`BACKLOG.md`、`HANDOFF.md`、`RIGHTS_LEDGER.md`、`research/` | 研究登记、Base 列表、游戏列表、当前焦点、授权范围、权限、运行状态 |
| Base | `.production/bases/<base-id>/` | Base ID、版本与各版本就绪度、核心能力、来源审查、扩展点、资产接口、构建与测试命令、已知限制、依赖它的游戏 |
| Game | `games/<game-id>/.production/` + `design/` | 游戏 ID、目标、绑定的 Base 版本、各阶段状态、就绪度、缺陷、当前 Agent 工作范围、下一步、发布状态 |

登记表只存 ID 和路径，详细状态以各层自己的文件为准，避免多份记录互相矛盾。设备相关内容只放在被忽略的 `.production/local/`。

## 目录示例
```text
my-studio/
├── AGENTS.md
├── .agents/skills/game-production/      # 固定版本的 Skill 副本
├── .production/
│   ├── WORKSPACE.json
│   ├── BACKLOG.md · HANDOFF.md · RIGHTS_LEDGER.md
│   ├── research/research-01/MECHANICS_MATRIX.md
│   ├── bases/core/BASE.json · GATES.json · CAPABILITIES.md · RIGHTS_LEDGER.md
│   └── local/ENVIRONMENT.json           # 不进 Git
├── engine/                              # Base 代码（位置由 code_path 决定，可以是 . 或 packages/core）
└── games/
    ├── game-01/
    │   ├── .production/GAME.json · GATES.json · ASSETS.json · BACKLOG.md · HANDOFF.md · RIGHTS_LEDGER.md · evidence/
    │   ├── design/GAME_DESIGN.md · ART_DIRECTION.md · ART_ASSET_PLAN.md · ANIMATION_SPEC.md · RELEASE_CHECKLIST.md
    │   └── config/ content/ assets/ build/  # 由引擎决定，只放本游戏内容
    └── game-02/ …
```
游戏代码目录的结构取决于引擎，工具不强制。原则只有一条：本游戏的配置、内容、资产、测试记录和构建产物都放在本游戏目录里。

## Base 版本与依赖
- `base register` 创建 1.0.0（或指定版本），就绪度为 NONE。
- Base 门禁 PASS 时写 `base_version`。`base update --readiness` 只能在当前版本的证据足够时提升。
- `base update --freeze` 冻结基线。冻结后的版本作为历史保留，旧游戏可以继续绑定它。
- `base bump --version 1.1.0 --summary "..."` 开启新版本，新版本就绪度为 NONE。工具会列出仍绑定旧版本、需要回归的游戏。
- `game rebind --base core@1.1.0` 改绑后，Q01–Q08 和 R01–R03 的 PASS 必须写新的 `base_version` 才算数。工具会降低就绪度声明，并把 G5/G6 标为 NEEDS_REWORK，直到回归证据补齐。

## Core 反哺流程
1. 在 `GAME.json core_extensions.proposed_for_base` 中记录需求和理由。
2. 判断它是不是通用机制，确认不会破坏现有接口。
3. 在分支或独立工作树中修改 Base，`base bump` 并写清是否破坏兼容。
4. 为新版本重跑 B03–B08；B08 必须覆盖所有依赖游戏的回归。
5. 依赖游戏逐个改绑并回归，或者明确继续使用旧版本。
6. 写入 `core_extensions.merged_into_base`，更新 CAPABILITIES.md 的版本表。

## 并行与隔离
- 多个 Agent 并行修改同一个 Base：使用独立分支或工作树，指定集成者；集成时对所有依赖游戏做回归。
- 多个 Agent 分别制作不同游戏：各自只写自己的 `games/<id>/`。改到 Base 时走上面的反哺流程。
- 游戏证据路径相对于游戏目录，`..` 会被拒绝。游戏的 JSON 记录中引用其他游戏的目录算错误，Markdown 中出现则给出警告。共享记录中不得出现 `C:\`、`/Users/`、`/home/` 等设备路径。
- 存档、本地存储键、包名和发布 ID 每款游戏独立，避免串档（Q06 检查）。

## 授权范围（run.scope）
- `target` 和 `basis`（用户原话）决定什么时候可以停止。`game_quota` 防止静默扩大范围。
- 用户后来新提出的游戏请求用 `game create --user-request "<原话>"` 记录，旧范围保存在 `scope_history`。
- `run --status TARGET_REACHED` 会按目标核对证据，不满足就拒绝。

## 旧工程适配
- v3 单游戏项目：用 `migrate` 原样保留 `.production/` 中的记录，并登记为 `layout: v3_legacy` 的游戏（路径 `.`）。以后可以把根目录的引擎 `base register --code-path .`，新游戏放到 `games/`。
- 结构不同的已有游戏：`game create --path apps/old-game --adopt-existing`，只补齐缺少的记录，不移动文件。
- 不强制把所有旧项目迁移到新目录结构。
