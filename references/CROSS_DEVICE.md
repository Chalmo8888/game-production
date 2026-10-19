# 跨 Agent、跨会话、跨设备与多游戏接续

## 推荐默认：仓库随项目走，单写入者接力
每个工作区仓库包含一份固定版本的 `.agents/skills/game-production/` 和全部 `.production/`、`games/*/` 记录。Skill 主副本单独管理，按版本升级；不要让某台机器上的全局 Skill 在无提示的情况下覆盖项目规则。

代码、可共享的资源、契约、任务和精简证据随项目同步。凭据、研究原件、缓存、node_modules、venv、编译 SDK 等不要随意同步。大型授权资产可以单独传输，但要附路径和哈希清单（ASSETS.json 中的 runtime_files 就是这份清单）；“Git 已同步”不能证明资产都在。

## 五种接力模式
| 模式 | 做法 |
|---|---|
| A 单 Agent 全流程 | `scope --target full_pipeline`，mode=auto。阶段完成后工具会提示继续下一阶段，直到目标的证据满足 |
| B 多 Agent 接力 | 每个 Agent 开始前读 WORKSPACE 和对应游戏的记录，用 `game update --assign-agent <label> --assign-stages G2` 记录分工，结束前写 HANDOFF 并运行 `handoff --check` |
| C 同一软件开新会话 | 读 WORKSPACE、HANDOFF、焦点游戏的 GAME.json 和 BACKLOG，运行 `status`，不依赖旧聊天 |
| D 跨设备 | 先核对代码、资产、Base 版本和本地工具（`env`），做最小构建和冒烟测试，再恢复任务 |
| E 多游戏 | 用 `focus --game <id> --stage <G?>` 明确切换；只写当前游戏的目录；Base 改动走版本和回归流程 |

Agent 的组合方式不做限制：A 做研究和 Base，B 做 Game 01 的策划与开发，C 做美术，D 做审查；也可以是两个或三个 Agent，顺序也可以不同。软件身份不写进规则，只记录在 assignment.agent_label 中作为说明。

## 设备 A 交出
完成当前的安全操作后停止写入。只提交本任务的改动（不把无关的未提交文件一起纳入），然后更新：
- 工作区 HANDOFF：焦点、授权范围、各 Base 与游戏的摘要、需要回归的依赖。
- 游戏 HANDOFF 与 GAME.json：当前阶段、assignment、next_action、具体缺陷、资产同步清单。
- 运行 `project.py handoff --game <id> --check`，结果为 COMPLETE 后再交出。
默认不 push；只有在明确预授权某个私有仓库或分支后，才能自动同步。

无法联网时，可以交付经过审查的项目快照和清单。使用 Git bundle 时，另附未提交、未跟踪文件和大资产的处理说明。不能只交 dist，也不能只交 Skill。

## 设备 B 接手
核对目标仓库或快照、本地已有的改动、缺失的资产与引用。运行 `project.py env --device-label <名称>` 重新探测，它只写本地文件，不改项目事实。按项目锁文件安装依赖，执行最小构建和冒烟测试。用 HEAD 和证据决定下一项任务，不根据旧聊天重新开始。

公共文件只用相对路径；校验器会拒绝共享记录中的 `C:\`、`/Users/`、`/home/` 等设备路径。前一台机器的 localhost URL 不能证明当前机器上的服务存在，需要重新启动并记录端口。不要改全局 PATH 来修复项目路径。

## 并行不是默认
同一个工作树有两个写入者会产生冲突。确实需要并行时：使用分支或独立工作树，明确任务 ID 和文件归属，固定资产契约版本，指定集成者，合并后重新 QA。
- 多个 Agent 修改同一个 Base：集成时对所有依赖游戏做回归（B08）。
- 多个 Agent 分别制作不同游戏：各写各的 `games/<id>/`，互不干扰。
- 不要用 force 覆盖别人的改动。

`WORKSPACE.run.active_session` 和 `GAME.assignment` 只是协作提示，不是跨设备的分布式锁。两台设备离线时，一个 JSON 无法自动互斥；写入归属没有确认之前，先只读审查，不同时写主分支。

## 工具和权限可以换，工作目标不换
这台机器能浏览但不能生图，下一台能生图但没有浏览器，都按各自的能力选择未被阻断的任务。切换软件不改变目标、验证状态或授权，也不会自动给新设备授予收费 API 或远程发布权限。

用户希望“这台做 G3、下一台做 G4/G5”时，使用 stage 模式和 assignment；其余情况使用 auto。单 Agent 不需要伪造交接给自己，保持同样的标准即可。
