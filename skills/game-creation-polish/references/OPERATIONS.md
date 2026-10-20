# 无人值守执行、状态记录与跨设备接力

## 统一原则
> 开始执行，直到达到当前目标可验证的交付要求，或遇到无法自行解决的真实外部阻断。
>
> 只要执行环境允许，在授权和预算范围内仍有有价值且可执行的工作，就继续开发、测试、检查、返工和扩展。普通技术决策自行处理，不需要用户进行阶段审批。
>
> 完成一个小功能、一个里程碑或一个版本，不构成自动停止条件。发现质量不达标，必须自主定位问题并返工。一个任务受阻，应继续其他不依赖该任务的工作。
>
> 不允许通过空循环、重复无意义操作或虚假汇报制造工作时长。会话或执行环境终止时保存真实检查点，不声称仍在后台执行。

## 无人值守 ≠ 扩大目标
授权范围记录在 `WORKSPACE.run.scope`（target、game_quota、用户原话 basis）：
- 用户要求完整的 Game 01（`scope --target game`）：持续推进 Game 01 的策划、开发、美术、QA 和交付，直到 RELEASE_CANDIDATE 或真实阻断。
- 用户要求连续制作三款（`--target batch --game-quota 3`）：按顺序完成约定的三款，每款中途不需要审批；做完第三款后停止。
- 用户只要求 G2 美术规划：stage 模式，`--allowed-stages G2`，充分执行并自审后按阶段交接（HANDOFF_READY）。
- 用户后来新增请求时，用 `game create --user-request` 记录原话，旧范围保存在 `scope_history`。
- 研究或建 Base 的目标（target research/base）属于 game-reverse-engineering，本工具会拒绝把它当作游戏目标完成。

未经授权不能付费、删除无关文件、推送项目、公开部署或进行危险操作。

## 每轮任务的五要素
选择一个能缩小重要差距的任务，写明预期产物、依赖、允许修改的范围、验收方法、失败后的替代路径。完成后保存产物和证据，再选下一项。优先处理崩溃、卡关、错误的伤害或状态、阻断资源生产的管线问题，然后才是必要的内容和表现。多款游戏并存时，不在未授权的游戏上花时间。

## 停止、交接与等待（`gcp.py run --status`）
- `TARGET_REACHED`：`run.scope` 定义的目标已满足。工具会核对游戏就绪度和 Base 交接，不满足就拒绝记录。
- `HANDOFF_READY`：用户只分配了阶段，阶段出口已满足。
- `EXTERNAL_BLOCKED`：授权范围内所有有价值的任务都因明确的外部条件无法继续。写明尝试过什么、为什么没有剩余可做的事、解除条件是什么。
- `RUNTIME_LIMIT`：宿主、上下文、额度或工具执行终止。只记录已知事实；原因不明就写未确认。
- `USER_PAUSED`：用户主动要求暂停或接手。

缺少生图能力时：把资产任务标为受阻，继续做契约、切图工具、测试、UI 布局、逻辑或其他内容。最后只剩正式资产时，交接未完成的资产，不宣称作品完整。缺少法务确认或真人体验时：继续能做的工作，直到只剩这些外部事项，然后交付候选并准确说明阻断。

## 预算、权限和防空转
WORKSPACE.permissions 可以预授权指定服务的消费上限、私有仓库同步、安装范围和允许写入的目录。未配置的付费预算视为零。本地 ENVIRONMENT 记录并发测试上限、命令超时和缓存目录；端口冲突就换空闲端口，只终止能确认由本任务启动的进程。不修改全局电源策略、全局 PATH 或其他工程的环境。

同一个失败默认最多用同一策略尝试 3 次；之后必须换假设、查看第一个错误、隔离最小复现或换任务。新增文档、重复测试、提高版本号都不算完成量。每完成一个实质任务、做风险改动前、会话余量不足时和交接前，都要保存检查点。

## Git 基线与变更保护
- 开始前记录 `git status` 与 HEAD；只提交本任务的改动，不把无关的未提交文件一起纳入；不 force push。
- 不修改 Base 核心与 starter 路径（交接中的 `core_paths`、`starter_paths`）。交接列出的文件哈希变化会让游戏失去 GAME_READY 资格。
- 风险改动在分支或独立工作树进行；合并后重新 QA。

## 状态记录
| 文件 | 作用 |
|---|---|
| `.production/WORKSPACE.json` | Base/游戏登记表（只存 ID 和路径）、焦点、授权范围 `run.scope`、运行模式与状态、权限 |
| `.production/bases/<id>/handoff/<version>/*-CREATOR_HANDOFF.json` | Base 的创作交接（由 game-reverse-engineering 写入，本 Skill 只读） |
| `games/<id>/.production/GAME.json` | brief、Base 绑定与改绑历史、G0–G7 阶段状态、就绪度、发布状态、assignment、缺陷摘要、下一步、retrospective |
| `games/<id>/.production/GATES.json` | D01–D02、Q01–Q08、R01–R04，游戏门禁状态的唯一来源 |
| `games/<id>/.production/ASSETS.json` | 资产状态（planned → verified）、运行时文件哈希、来源和许可 |
| `games/<id>/.production/BACKLOG.md · HANDOFF.md · RIGHTS_LEDGER.md` | 任务、交接、来源 |
| `games/<id>/design/` | GAME_DESIGN、ART_DIRECTION、ART_ASSET_PLAN、ANIMATION_SPEC、RELEASE_CHECKLIST |
| `.production/local/ENVIRONMENT.json` | 仅本机：绝对路径、工具、版本、端口、缓存。不提交 Git，不存密钥 |

声明的就绪度只能低于或等于证据支持的级别；`validate` 只说明记录结构、证据哈希和就绪度声明一致，不判断游戏品质或法律问题。

## 跨 Agent、跨会话、跨设备
- **单写入者接力**：仓库带固定版本的 `.agents/skills/game-creation-polish/` 和全部记录。凭据、研究原件、缓存、依赖目录不随意同步；大型授权资产单独传输时附路径和哈希清单（ASSETS.json 的 runtime_files）。
- **多 Agent 接力**：开始前读 WORKSPACE 和对应游戏记录，用 `game update --assign-agent <label> --assign-stages G2` 记录分工；结束前写 HANDOFF 并运行 `handoff --game <id> --check`，结果 COMPLETE 再交出。
- **新会话**：读 WORKSPACE、HANDOFF、焦点游戏的 GAME.json 和 BACKLOG，运行 `status`，不依赖旧聊天。
- **跨设备**：先核对代码、资产、Base 交接和本地工具（`gcp.py env --device-label <名称>` 只写本地文件），做最小构建和冒烟测试，再恢复任务。前一台机器的 localhost URL 不能证明当前机器上的服务存在。
- **多游戏**：用 `focus --game <id> --stage <G?>` 明确切换；只写当前游戏的目录。

公共文件只用相对路径；校验器会拒绝共享记录中的 `C:\`、`/Users/`、`/home/` 等设备路径。`run.active_session` 和 `GAME.assignment` 只是协作提示，不是分布式锁；写入归属没有确认之前，先只读审查。

## 不提供不存在的持续运行能力
本包不带定时器、自动重发消息、无限命令循环或跨软件调用器。当前 Agent 活跃期间按合同持续推进；会话结束后能否再次唤醒，取决于实际宿主能力或外部调度服务。
