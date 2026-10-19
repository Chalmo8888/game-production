# v1 → v3：不重做游戏，只迁移流程

> 当前版本为 v4。v1 项目先按本文迁移到 v3 的记录结构，再用 `project.py migrate` 升级到 v4（见 [MIGRATION_V3](MIGRATION_V3.md)）。文中“START/STAGE/REVIEW”分别对应 v4 的 START_FULL_PIPELINE、STAGE/ART_PRODUCTION、REVIEW_GAME。

v1 将开发/资源合同写给 Cursor，美术/QA 写给 Codex，且若干提示词引用了未配套的任务文件。v2 已删除工具身份分配，提供统一状态和初始化工具。

## 安全迁移
1. 确认没有其他 Agent 在改同一工作树，保存当前代码、资产、Git 状态及任务。
2. 把 v3 安装到 `.agents/skills/game-production/`。若同路径已有不同内容，工具会拒绝覆盖；先查看差异、备份到不会被自动发现的项目外存档，再由 Agent 合并安装。
3. 从旧 PROJECT_BRIEF、PROGRESS、QUALITY_GATES、ART_HANDOFF、RIGHTS_LEDGER 等读取事实，映射到 `.production/`。不要仅按标题复制 PASS；核验当前版本和证据。
4. 旧 v1 `CURSOR_MASTER` 意图改为 START/auto；旧 `CODEX_ART` 改为 STAGE/S4；旧 `CODEX_QA` 改为 REVIEW；RESUME 使用新版本。不保留互相冲突的两套自动执行规则。
5. 旧目录含项目事实时保留并标明历史来源；将其工具绑定规则移出激活入口，不静默删除源码/文档。旧 Skill 的自动发现位置和根 AGENTS 指向需检查。
6. 已经完成实现的游戏，如已有可玩游戏，优先现有资源管线→正式资产→回归→候选；不要从 S1 重做逆向或新建商业引擎。

同一 Skill 不要在 `.agents/skills`、`.cursor/skills` 和用户目录放多个不同版本。项目副本固定版本，升级只在安全检查点进行。
