# 从旧版 totop-game-production v2 迁移到 game-production v3

这是 Skill **改名与去平台绑定**，不是创建新游戏。若旧项目正在由 Agent 执行，先在稳定检查点停止旧会话并保存工作树。

1. 保存当前游戏、Git 状态、项目 `.production/`、权利记录与证据。不要删除任何真实游戏文件。
2. 审核旧 `.agents/skills/totop-game-production/` 与根目录 `AGENTS.md` 里的版本化工作流块，复制项目事实，移除或停用旧规则的自动发现入口。此步骤必须审查再做，不能静默覆盖。
3. 将 v3 `game-production/` 放入 `.agents/skills/game-production/`。如果要执行 `project.py init`，确认旧路径/旧 AGENTS 规则已完成安全迁移；脚本会拒绝旧规则并存。
4. 保留 `.production/` 数据。该版沿用 schema `2.0`；`kit_version` 可以经确认后更新到 `3.0.0`，但不改变用户目标、不把失败门禁自动设为 PASS。
5. 如旧项目特指某平台的 SDK 和 H5，保留在 `.production/PROJECT.json` 的平台合同中，不强制改成泛化目标。
6. 检查本机路径、缓存、权限、发布目标，跑 `project.py validate`，再恢复 Agent 执行。

对于全新项目无需迁移，可直接 init。
