# 阶段合同与非线性推进（v4）

执行者统一称“当前 Agent”。它可以自行串行切换研究者、实施者、策划、美术、审查者的职责，不要求特定产品或多个账号。阶段可以交叉；证据仍有效时可复用；缺口回到相关阶段，不是每次都从头开始。

## R0 Project Intake
输入：用户最终目标、原游戏或参考链接、目标平台、授权边界、已有工程、当前目录、可用工具。
动作：区分三种路线并写入 `WORKSPACE.intake.route`：
- `new_research`：从原游戏/开源项目开始研究并建立 Base。
- `adopt_existing`：接管已有工程，先审查现有游戏、资源工具和未通过项；工程可以登记为 Base、游戏，或作为 v3 遗留游戏保留。
- `new_game_on_base`：已有 Base，直接从 G0 开始。
把用户原话记入 `run.scope.basis`，并确定 target 与 game_quota。
出口：路线、授权范围和第一批可执行任务清楚。不把“参考成熟机制”变成从零编一个贫乏 Demo。

## R1 Research & Reverse Engineering（按需）
优先使用用户已有的文件和有效研究，再查外部公开资料。准确说明读取到的是原始源码、反编译恢复物、格式化 bundle 还是独立实现。
研究范围按需选择：源码和程序结构、机制与状态机、数值与配置、单位/敌人/角色行为、关卡结构、动画与资源管线、原版运行行为、技术依赖、商业授权边界。
产物：`.production/research/<id>/MECHANICS_MATRIX.md`，包含版本/哈希、位置、规则、参数单位、调用关系、可达范围和缺口。保留 VERIFIED / STATIC_ONLY / INFERRED / PROXY / UNKNOWN 的区分。恢复了运行时的资源组织，不等于恢复了作者的原始美术工程。
出口：B01 PASS，Base 达到 RESEARCH_READY。研究服务于已锁定的目标，不为“完全逆向”无限分析与目标无关的部分。

## R2 Reusable Core / Base
内容：核心玩法；数据与配置接口；资源与动画接口；关卡及内容扩展接口；构建与测试工具；示例运行内容；兼容性与版本记录。
有合法授权的现成源码，优先复用与适配；不能合法迁移的实现，只保留通用机制结论，用权利清晰的方式独立实现。不默认重写引擎。
产物：`.production/bases/<id>/` 下的 BASE.json（版本、能力、扩展点、资产接口、命令、限制）、GATES.json（B01–B08）、CAPABILITIES.md、RIGHTS_LEDGER.md。
出口：
- BASE_READY：B03–B08 PASS（或带依据的 NOT_APPLICABLE），B01 满足，B02 不是 FAIL，且这些 PASS 都是针对当前版本验证的。
- COMMERCIAL_BASE_CANDIDATE：在此基础上 B02 严格 PASS。法律审查可能仍待完成。
- 冻结：`base update --freeze` 把当前版本设为基线，后续改动走新版本。

## G0 New Game Creation
`game create --id <slug> --base <base>@<version>` 在 `games/<slug>/` 下创建独立记录与 design 模板，绑定 Base 版本，并把这款游戏加入授权范围。不复制引擎代码。超出 game_quota 时，必须有用户的明确请求。目录结构不同的旧工程用 `--path` / `--adopt-existing` 非破坏性登记。

## G1 Game Design / 游戏策划
在大量内容开发和美术生产之前完成。按 [GAME_DESIGN_GUIDE](GAME_DESIGN_GUIDE.md) 编写 `design/GAME_DESIGN.md`，包括定位、用户、核心体验、世界观、循环、继承与改良、操作、玩法主体、技能道具、经济成长、关卡难度、Boss/事件、UI、规模与顺序、验收标准，再加上 Base 依赖划分和开发任务。不适用的节写明原因。
出口：D01 PASS（工具检查模板标记已删除、17 节齐全）。策划内容已转化为配置需求、行为规格和可验证的开发任务（写入游戏 BACKLOG）。

## G2 Art Direction & Production Planning / 美术策划
按 [ART_DIRECTION_GUIDE](ART_DIRECTION_GUIDE.md) 编写 ART_DIRECTION、ART_ASSET_PLAN、ANIMATION_SPEC。开始前必须读取 Base 的真实资产接口，不得要求引擎不支持的格式。说明怎样生产、加工、导入和验证，而不只是写一句“高质量手绘风格”。
先选一个有代表性的角色/单位和一个场景，走完“需求 → 制作 → 加工 → 导入 → 动作 → 实机 → 逻辑回归”的完整链路，在 `ASSETS.json` 中标为 verified 后再批量扩展。
出口：D02 PASS。美术明确不在范围内时，G2 和 D02 标 NOT_APPLICABLE 并写依据，同时保留资产契约。

## G3 Game Implementation / 内容开发
依据策划和 Base 开发，优先复用 Core 已有能力。游戏专有的逻辑、配置和数据放在游戏目录。需要新增通用机制时，先判断属于游戏扩展还是 Core 功能，记录到 `GAME.json core_extensions`。反哺 Core 走 Base 新版本，保证接口兼容，并对其他依赖游戏做回归。
出口：Q01（逻辑）、Q02（内容与差异）有证据；其他游戏的回归不退化。

## G4 Art & Audio Production / 资产制作与集成
按 G2 的计划执行。允许使用生图、建模、动画、脚本加工、音频生成等合法工具；可以由当前 Agent 全做，也可以交给另一个 Agent，或一台设备生成、另一台设备集成，分批替换，直接复用已有的合法资产。
资产状态依次为：planned → source_generated → processed → integrated → verified（或 rejected）。“图片已经生成”只是 source_generated。
出口：范围内玩家可见的资产都已 verified；没有静默回退到占位资源。

## G5 Game QA & Iteration
完整 QA：游戏逻辑、真实操作、关卡通关、武器和单位差异、数值平衡、动画自然度、视觉一致性、地图与碰撞、UI/UX、音效、存档、性能、不同分辨率、内容完整度、资源许可。对应 Q01–Q08。
质量不达标时自主返回对应的开发、策划或美术阶段修复（阶段标为 NEEDS_REWORK）。技术测试通过不等于游戏品质通过；没有独立审查者时如实记录 self_review。
出口：GAME_READY（工具会核对 D/Q 门禁和 Base 就绪度）。

## G6 Release Candidate
为这款游戏生成独立的发行候选包。根据目标平台选择打包器或发布适配器，不固定为某个平台。按 `design/RELEASE_CHECKLIST.md` 执行，用 `game update --artifact` 记录产物哈希。
分别记录以下状态，不能互相替代：功能完成（FEATURE_COMPLETE）、QA 完成（GAME_READY）、技术发行候选就绪（RELEASE_CANDIDATE）、权利审查就绪（R03）、用户批准公开发布（R04 → PUBLICATION_APPROVED）。
出口：RELEASE_CANDIDATE。未经授权不得公开发布。

## G7 Next Game / 批量生产
写 `GAME.json retrospective`：使用的 Base 版本、可复用的新增能力、资产生产经验、QA 经验、兼容性问题、已反哺 Core 的改动。
之后用户只需说“基于这个 Base 开始制作第二款游戏，主题为 XXX”，Agent 就会：检查现有 Base 和游戏列表 → 创建 `games/<slug>` → 建立独立状态 → 从 G1/G2 开始 → 开发 → 完整 QA → 独立打包。不重复已经完成且仍有效的逆向工作。

## 阶段跳过与回退
- 有效证据覆盖当前版本时，可以复用对应阶段。
- 用户明确不需要的能力可以标 NOT_APPLICABLE，并写明依据；工具缺失不是 NOT_APPLICABLE 的理由。
- 依赖变化导致证据过期时，只回退受影响的部分（例如改绑 Base 后，G5/G6 会变为 NEEDS_REWORK）。
- 审查发现一个缺陷，不意味着要把不相关的已验证机制全部重做。

## 从 v3 阶段的对应关系
S0 → R0；S1 → R1；S2 → R2（通用部分）+ G3（游戏部分）；S3 → R2 资产接口 + G2 代表资产；S4 → G4；S5 → G5；S6 → G6。v3 遗留游戏可以继续使用 S 阶段记录。
