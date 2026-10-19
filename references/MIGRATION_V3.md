# v3 → v4：保留单游戏成果，启用 Base 与多游戏

v3 的项目是一个单游戏工作区：`.production/` 下有 PROJECT、STATE、GATES、BACKLOG、HANDOFF、RIGHTS_LEDGER 和 evidence，以及 `.agents/skills/game-production/` 的 v3 副本。v4 增加了工作区层、Base 层和 `games/<id>/` 层。迁移不改动 v3 已有的任何一条事实。

## 自动迁移（推荐）
1. 确认没有其他 Agent 正在写这个工作树，保存当前的代码、资产和 Git 状态。
2. 用新版 Skill 中的脚本执行：
   `python <新版 skill>/scripts/project.py migrate --project <游戏根目录> [--game-id old-game]`
3. 迁移会做以下事情：
   - 校验已安装的 v3 Skill 副本是否与它自带的 SHA256SUMS 一致。有本地改动或多出文件时会拒绝迁移；确认后可以加 `--accept-archive` 继续。
   - 把旧 Skill 副本完整复制到 `.production/archive/v3-to-v4-<时间>/skill-3.0.0/`（不会被 Agent 自动发现），核对文件数量后再替换为 v4。
   - 只替换 AGENTS.md 中的 v3 Game Production 块，其他团队规则保留；原文件另存为存档。
   - 创建 `.production/WORKSPACE.json`，把原游戏登记为 `layout: v3_legacy` 的游戏（路径 `.`，记录 `.production`），并复制原 PROJECT 中的权限、STATE 中的模式/状态/下一步和阶段（S0–S6）。
   - **v3 的 PROJECT/STATE/GATES/BACKLOG/HANDOFF/RIGHTS_LEDGER/evidence 字节完全不变**，原有的 PASS 证据继续按哈希校验。
4. 运行 `project.py validate --project <根目录>` 和 `status`，确认原有任务、下一步和证据都在。

## 迁移之后
- 原游戏可以继续按 v3 的 S 阶段推进，校验器使用 v3 规则检查它的记录。
- 原工程的引擎值得复用时，先审查来源（B02），再执行 `base register --id core --version 1.0.0 --code-path .`（或引擎所在的子目录），补齐 B01–B08。
- 新游戏用 `game create` 放到 `games/<id>/`。需要超出原授权范围时，记录用户的明确请求（`--user-request`）。
- 原游戏以后也可以手动整理成 v4 游戏记录，但这不是必需的，也不会被强制执行。

## 手动迁移的要点
无法运行脚本时：保留 `.production/` 不动，按 `templates/WORKSPACE.json` 手写 WORKSPACE，把原游戏登记为 v3_legacy；把旧 Skill 副本移到不会被自动发现的存档目录，再放入 v4；只替换 AGENTS.md 中的 v3 块。不要把 PASS 按标题照抄到新的门禁文件里。

## v3 概念的对应关系
| v3 | v4 |
|---|---|
| PROJECT.delivery_target | WORKSPACE.run.scope.target（release_candidate → game，creator_base → base，research_handoff → research） |
| STATE.run | WORKSPACE.run（工作区）+ GAME.json stages（每款游戏） |
| G01–G10 | Base B01–B08 + Game D01–D02/Q01–Q08 + Release R01–R04 |
| S0–S6 | R0–R2 + G0–G7（见 STAGES 末尾的对应表） |
| creator_base 目标 | 一等公民 Base，带版本、冻结和依赖回归 |
