# 游戏阶段合同（G0–G7）与非线性推进

执行者统一称“当前 Agent”。它可以自行串行切换策划、美术、实施者、审查者的职责，不要求特定产品或多个账号。阶段可以交叉；证据仍有效时可复用；缺口回到相关阶段，不是每次都从头开始。

研究与 Base 建设（原 R0–R2）属于 [game-reverse-engineering](../../game-reverse-engineering/SKILL.md)。本 Skill 从一个已交付的 Base 开始；Base 还不存在或交接不完整时，先回到逆向 Skill，不在这里补做研究。

## G0 New Game Creation
`gcp.py game create --id <slug> --base <base>@<version> --user-request "<用户原话>"` 在 `games/<slug>/` 下创建独立记录与 design 模板，绑定 Base 版本，并把这款游戏加入授权范围。不复制引擎代码。超出 game_quota 时，必须有用户的明确请求。目录结构不同的已有游戏用 `--path` / `--adopt-existing` 非破坏性登记。
开始前读 Base 的 START_HERE、BASE_HANDOFF 和最新创作交接（`gcp.py status` 会显示交接等级、两类保真度和独立复用状态）。

## G1 Game Design / 游戏策划
在大量内容开发和美术生产之前完成。按 [GAME_DESIGN_GUIDE](GAME_DESIGN_GUIDE.md) 编写 `design/GAME_DESIGN.md`，包括定位、用户、核心体验、世界观、循环、继承与改良、操作、玩法主体、技能道具、经济成长、关卡难度、Boss/事件、UI、规模与顺序、验收标准，再加上 Base 依赖划分和开发任务。不适用的节写明原因。
出口：D01 PASS（工具检查模板标记已删除、17 节齐全）。策划内容已转化为配置需求、行为规格和可验证的开发任务（写入游戏 BACKLOG）。

## G2 Art Direction & Production Planning / 美术策划
按 [ART_DIRECTION_GUIDE](ART_DIRECTION_GUIDE.md) 编写 ART_DIRECTION、ART_ASSET_PLAN、ANIMATION_SPEC。开始前必须读取 Base 创作者工具包中的场景几何、角色规范、图层规则和动画导入规则，不得要求引擎不支持的格式。说明怎样生产、加工、导入和验证，而不只是写一句“高质量手绘风格”。
先选一个有代表性的角色/单位和一个场景，走完“需求 → 制作 → 加工 → 导入 → 动作 → 实机 → 逻辑回归”的完整链路，在 `ASSETS.json` 中标为 verified 后再批量扩展。
出口：D02 PASS。美术明确不在范围内时，G2 和 D02 标 NOT_APPLICABLE 并写依据，同时保留资产契约。

## G3 Game Implementation / 内容开发
依据策划和 Base 开发，优先用 Base 的内容包工具、配置和扩展点。游戏专有的逻辑、配置和数据放在游戏目录。需要新增通用机制时，先判断属于游戏扩展还是 Base 能力，记录到 `GAME.json core_extensions`；Base 能力回报给 game-reverse-engineering，不在游戏里直接改 Base 核心。
出口：Q01（逻辑）、Q02（内容与差异）有证据；其他游戏的回归不退化。

## G4 Art & Audio Production / 资产制作与集成
按 G2 的计划执行。允许使用生图、建模、动画、脚本加工、音频生成等合法工具；可以由当前 Agent 全做，也可以交给另一个 Agent，或一台设备生成、另一台设备集成，分批替换，直接复用已有的合法资产。导入前用 Base 的资产校验器检查。
资产状态依次为：planned → source_generated → processed → integrated → verified（或 rejected）。“图片已经生成”只是 source_generated。
出口：范围内玩家可见的资产都已 verified；没有静默回退到占位资源。

## G5 Game QA & Iteration
完整 QA：游戏逻辑、真实操作、关卡通关、武器和单位差异、数值平衡、动画自然度、视觉一致性、地图与碰撞、UI/UX、音效、存档、性能、不同分辨率、内容完整度、资源许可。对应 Q01–Q08（[QUALITY](QUALITY.md)）。
质量不达标时自主返回对应的开发、策划或美术阶段修复（阶段标为 NEEDS_REWORK）。技术测试通过不等于游戏品质通过；没有独立审查者时如实记录 self_review。
出口：GAME_READY（工具会核对 D/Q 门禁和 Base 创作交接）。

## G6 Release Candidate
为这款游戏生成独立的发行候选包。根据目标平台选择打包器或发布适配器，不固定为某个平台。按 `design/RELEASE_CHECKLIST.md` 执行，用 `game update --artifact` 记录产物哈希。
分别记录以下状态，不能互相替代：功能完成（FEATURE_COMPLETE）、QA 完成（GAME_READY）、技术发行候选就绪（RELEASE_CANDIDATE）、权利审查就绪（R03）、用户批准公开发布（R04 → PUBLICATION_APPROVED）。
出口：RELEASE_CANDIDATE。未经授权不得公开发布。

## G7 Next Game / 批量生产
写 `GAME.json retrospective`：使用的 Base 版本、可复用的新增能力、资产生产经验、QA 经验、兼容性问题、需要回报 Base 的改进（`core_feedback`）。
之后用户只需说“基于这个 Base 开始制作第二款游戏，主题为 XXX”，Agent 应按这个顺序推进：检查 Base 交接和游戏列表 → 创建 `games/<slug>` → 建立独立状态 → 从 G1/G2 开始 → 开发 → 完整 QA → 独立打包。不重复已经完成且仍有效的研究。预览版中这些步骤由 Agent 自己执行，`gcp.py` 只负责记录和校验；这个流程尚未在真实游戏上端到端验证过。

## 阶段跳过与回退
- 有效证据覆盖当前版本时，可以复用对应阶段。
- 用户明确不需要的能力可以标 NOT_APPLICABLE，并写明依据；工具缺失不是 NOT_APPLICABLE 的理由。
- 依赖变化导致证据过期时，只回退受影响的部分（例如改绑 Base 后，G5/G6 会变为 NEEDS_REWORK）。
- 审查发现一个缺陷，不意味着要把不相关的已验证机制全部重做。
