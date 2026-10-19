# Changelog

## game-reverse-engineering 1.1.0（2026-10-19，发布前补强）
1.1.0 只做加法，数据格式仍是 `gre-1.0`：1.0.0 的记录可以直接读取，`gre.py upgrade` 只补字段，不改已有值。
- **游戏特有能力发现**：38 个通用条目只是起始清单。新增 `gre.py discover`，要求从代码、运行、资源三类来源审查，结论为 DONE 或 UNAVAILABLE（须写原因）；新增 `parity add --source` 登记发现的条目，并附发现位置的证据。条目范围分为 core / optional / legacy / excluded，降级或排除都要写理由。三类来源都处理完才能达到 LOGIC_READY。
- **能力来源分类**：PARITY / REPLACEMENT / EXTENSION。PARITY 只能用于原版证据为 VERIFIED 或 STATIC_ONLY 的条目；UNKNOWN 的能力只能显式标为 EXTENSION 才能实现；REPLACEMENT 必须写差异，EXTENSION 必须有设计说明。报告和状态分别统计三类数量。
- **Creator 生产能力测试**：
  - 视觉资产重合不超过 20%，公共字体、工具和基础资源可以放进 shared_files 共用；
  - 每套配置至少一项通过配置或扩展接口实现的玩法改动（`probe-gameplay`，必须涉及 L1–L5 或 C1）；
  - 用正常输入跑通完整循环：开始 → 游玩 → 胜/负 → 结算 → 重开（`probe-loop`）；
  - 全部有运行时证据，并运行在同一个核心指纹上；测试素材不得来自隔离材料。
  只换图片的配置被列为 visual-only，不能证明生产能力。
- **QA 绑定代码**：VERIFIED 记录相关代码的指纹（`code_paths`，默认是整个核心）和 Git HEAD；相关代码改动后旧 QA 自动过期，状态中列为 stale。
- **价值驱动排序**：新增 `gre.py next`，按影响、是否阻碍下一等级、对新游戏的价值、证据是否充分和成本排序，并给出建议动作。研究预算（每条目默认 3 次）用完后拒绝继续研究，建议改用成熟组件（REPLACEMENT）或 EXTENSION。高分缺口未完成时，连续第 5 个打磨或文档任务被拒绝（POLISH_BLOCKED，可写理由覆盖）。新增 NEGLECTED_GAP 警告。
- **超时安全恢复**：`task start` 可以记录 pid 和命令；新增 `task recover --recover-action restart|abandon`，只允许处理已超时的任务（或 `--force` 并写明原因），任务记为 TIMED_OUT 并计入失败次数。
- **执行边界**：REUSE 模块新增 `execution`（never / sandboxed / reviewed）和 `execution_note`；隔离材料只能 never 或 sandboxed；核心路径不能位于 `research-private/`。
- **权利拆分为三项**：RE01（第三方代码许可）、RE03（原作素材与具体表达的使用权，只能由权利人批准，role 为 rights_holder）、RE02（用户公开发布批准，role 为 user，不能替代权利人授权）。状态显示“发布权利记录完整/不完整”，并始终注明“不是法律意见，剩余风险不为零”。
- **测试与性能**：测试增至 31 个；同一次快照内缓存条目检查和等级推导。

## 仓库 2026-10-19：新增 game-reverse-engineering 1.0.0；game-production 4.1.0
仓库变为多 Skill 结构。根目录仍然是 game-production，新的独立 Skill 放在 `skills/` 下。

**game-reverse-engineering 1.0.0（新增，`skills/game-reverse-engineering/`）**
- 面向 2D 游戏的逆向与 Base 建设：E0 技术调查 → E1 授权与复用判断 → E2 源码与动态行为研究 → E3 完整能力提取 → E4 逻辑系统 → E5 2D 表现系统 → E6 Creator 验证 → E7 交付。单个 Agent 可以独立完成。
- 能力等价矩阵（`re/PARITY.json`）覆盖 15 个能力域、38 个预置条目，并区分原版证据等级与 Base 能力状态。只有带测试、运行时或测量证据的 VERIFIED 才计入等级；INTERFACE_ONLY 和 DOCUMENTED 不计入；表现类条目必须有运行时或测量证据。
- 交付等级 LOGIC_READY → PRESENTATION_READY → CREATOR_READY。Creator Ready 要求两套差异明显的原创测试配置（文件哈希不重叠）运行在指纹相同的核心上。权利另设门禁：来源审查用 v4 B02，商业许可 RE02 只接受外部批准。
- 复用评估（`re/REUSE.json`，门禁 RE01）：KEEP/ADAPT 需要许可证据；反编译原作代码没有书面授权时只能 QUARANTINE；隔离材料不得进入核心路径，也不能作为实现来源。
- 无人值守与恢复：任务超时（STALLED）、重复失败、研究空转、打磨空转四种防护；证据和报告按时间戳另存，HISTORY.jsonl 只追加，删改历史会被发现；提供检查点、接续、交接检查和 Agent 分工记录。
- 规则吸收了《二战前线》《植物大战僵尸》《勇者之路》三个项目的经验，证据与推断分开标注（`references/LESSONS.md`）。
- `gre.py` 只用标准库，可以在空文件夹、已有工程或 v4 工作区上初始化；在 v4 工作区上只新增 `re/` 记录，v4 文件保持字节不变。
- 21 个自动化测试，并对 4 个关键防护做了变异检查。

**game-production 4.1.0**
- 版本号更新为 4.1.0（`kit_version`）；R0–R2、SKILL.md、START_RESEARCH 和 README 中增加指向 game-reverse-engineering 的入口。旧入口全部保留。
- 根目录 `SHA256SUMS.txt` 只覆盖 game-production 自身的发布文件，不包含 `skills/`，避免 v4 `init` 把其他 Skill 嵌套安装进项目。
- README 改为多 Skill 首页，直接提供 game-reverse-engineering 的完整启动提示词。

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
