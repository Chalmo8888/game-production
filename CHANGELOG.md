# Changelog

## v4.0.0 (2026-10-19)
结构性升级：从“单款游戏全流程”升级为“一个研究基座连续生产多款独立游戏”。v3 的能力全部保留：Agent 不绑定、自动推进、无人值守、严格门禁、跨设备、状态持久化、来源审查、接管已有项目、独立 QA 与返工、权限限制。

- **两个循环**：循环 A（R0 Intake → R1 研究 → R2 可复用 Base）只做一次；循环 B（G0 新建 → G1 游戏策划 → G2 美术策划 → G3 开发 → G4 美术音频 → G5 QA → G6 发行候选 → G7 复盘）每款游戏做一遍。
- **三层状态**：`.production/WORKSPACE.json`（授权范围、焦点、登记表）、`.production/bases/<id>/`（版本化 Base，就绪度为 RESEARCH_READY / BASE_READY / COMMERCIAL_BASE_CANDIDATE，支持冻结和依赖游戏列表）、`games/<id>/`（独立的 GAME.json、门禁、ASSETS.json、策划与美术文档）。schema 升到 3.0。
- **新增正式阶段**：G1 游戏策划（GAME_DESIGN 17 节，包括 Base 依赖划分和开发任务）、G2 美术策划（ART_DIRECTION / ART_ASSET_PLAN / ANIMATION_SPEC，加上代表资产的运行时验证）。新增规范 `GAME_DESIGN_GUIDE.md`、`ART_DIRECTION_GUIDE.md`、`BASE_AND_GAMES.md`。
- **三层门禁**：Base B01–B08、Game D01–D02/Q01–Q08、Release R01–R04，互不替代。门禁 PASS 绑定 Base 版本；就绪度声明不能超过证据；R04 只能是 external_approval。
- **授权范围**：`run.scope`（research / base / game / full_pipeline / batch，加上 game_quota 和用户原话）。超出范围创建游戏必须有 `--user-request`；目标未满足时拒绝记录 TARGET_REACHED。
- **新增启动提示词**：START_RESEARCH、START_FULL_PIPELINE、START_NEW_GAME、CONTINUE_GAME、ART_PRODUCTION、REVIEW_GAME、BATCH_PRODUCTION。RESUME、ADOPT_EXISTING、STAGE、HANDOFF 更新为 v4；START 和 REVIEW 保留为 v3 链接兼容页。
- **README 重写**：首页直接提供研究、新建游戏、一次性完整生产三段完整提示词，以及工作流图、Agent 组合、跨设备、目录示例、质量与版权边界。
- **project.py 重写**：新增 `migrate`、`research`、`base register|bump|update`、`game create|stage|update|rebind`、`focus`、`scope`、`run`、`env`、`status`、`handoff --check`；校验目录隔离、跨游戏引用、设备绝对路径、资产状态和哈希。
- **安装修复**：`init` 改为只安装 SHA256SUMS 清单中的文件（v3 会把 Skill 目录下的所有文件，包括 `.git/` 和临时文件，一起拷进项目），并校验包完整性。新增 `.gitattributes`（强制 LF）；Windows 上 `core.autocrlf` 产生的 CRLF 副本也能通过校验，并以 LF 安装。
- **v3 迁移**：`migrate` 让 v3 记录保持字节不变，登记为遗留游戏；旧 Skill 副本先存档再替换；只替换 AGENTS.md 中的 v3 规则块。
- v3 的 PROJECT/STATE/GATES 模板移到 `templates/v3/`，供遗留校验和迁移测试使用。

## v3.0.0 (2026-10-19)
- 将 Skill 从特定平台/组织去品牌化：`game-production`，面向独立开发者和团队。
- 阶段、无人值守主循环、来源边界、跨 Agent/设备交接、证据门禁保持不变。
- 发行目标不再强制任何特定网站、SDK 或 H5；由项目范围决定。
- 初始化脚本拒绝与旧版 `totop-game-production` 自动发现规则并存，需按迁移文档人工检查。
- GitHub 通用仓库根目录安装与隐私/许可证建议。

## v2.0.0
- 阶段式、多 Agent、项目状态机与 QA 门禁。
