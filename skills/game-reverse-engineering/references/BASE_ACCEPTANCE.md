# Base 验收规则

## 1. 交付等级（互不替代，由证据推导）
| 等级 | 含义 | 条件（工具核对） |
|---|---|---|
| LOGIC_READY | 玩法逻辑可以作为成熟基础使用 | RE01 PASS（复用评估完成，无 REVIEW）；游戏特有能力的发现已覆盖代码、运行和资源三类来源（或注明无法获得）；L1–L6 全部 core 条目 VERIFIED 或带依据 N/A；L1、L2、L5、L6 各至少一个 VERIFIED |
| PRESENTATION_READY | 2D 表现体系完整可用，并按原版方法继承或重建了场景装配、动画、渲染和资源控制能力 | + P1–P8 全部 core 条目满足要求，每个域至少一个 VERIFIED，表现证据为运行时录制或测量；**Presentation Reconstruction Gate 通过**（[PRESENTATION_2D 第 5 节](PRESENTATION_2D.md)） |
| CREATOR_CANDIDATE | 创作者可以在不研究原版、不改核心的情况下开始做新内容（尚未经过独立验证） | + C1 全部满足；两套有效的 Creator 生产能力测试配置；core 能力 `reusable_for_new_games = true`；**解耦门禁、创作者工具包、干净首次使用门禁通过**；核心与 starter 没有未提交改动 |
| CREATOR_READY | 另一个 Agent 只靠交付文档就做出了可玩切片 | + 最近一次**独立复用验收** PASS |

- 所有 VERIFIED 都必须绑定当前 Base 版本和相关代码指纹。核心代码改动、Base 升级或调查结论更正后，相关条目过期，等级需要重新验证。
- 等级只能用 `gre.py level --set` 声明，证据不足时会被拒绝；手动改写声明会被 `validate` 发现。旧版本规则下做出的声明只给出提示，不会让旧项目报错。
- 不需要制作正式的 Game 01，也不需要商业级美术。

## 2. Creator 生产能力测试
这是 Base 的生产能力测试，不是提前制作 Game 01。每套测试配置（probe）用以下命令记录：
1. `gre.py probe`：配置文件、**场景配置**（`--scene`，用 PX01 验证过的场景配置机制组装，两套不能相同）、**视觉资产**（本配置专有）、**共用资源**（`--shared`）、五类替换的运行时证据（角色、动画、单位、地图、视觉风格）和核心指纹。
2. `gre.py probe-gameplay`：至少一项具有实际意义的玩法改动。它必须引用 L1–L5 或 C1 中的条目，通过配置文件或既有扩展接口实现，并有运行时证据。只改表现的不算。
3. `gre.py probe-loop`：用原创测试素材、以正常输入（不跳关、不无敌、不强制胜利）跑通一个短小但完整的循环：开始 → 游玩 → 胜或负 → 结算 → 重开，并附录像或运行时录制。

一套配置有效的条件：针对当前 Base 版本，所有文件存在且哈希一致；内容放在 `core_paths` 之外，并且不来自隔离的研究材料；资产替换、玩法改动和完整循环都有运行时证据；核心指纹等于当前核心。

两套配置之间还必须满足：视觉资产按哈希计算的重合比例不超过 `max_visual_overlap`（默认 20%，共用资源不计入）；玩法配置不能完全相同；每类替换的证据各不相同；两套都运行在指纹相同的核心上。**只换图片、没有玩法改造的配置不能证明完整生产能力。**

## 3. 创作者门禁（CREATOR_CANDIDATE）
### 3.1 解耦门禁
- 在 RE_STATE 中声明 `starter_paths`（随 Base 交付、可替换的示例内容）。starter 不能放在 `core_paths` 之内。
- 工具从 starter 的 JSON（id、name、title、key、label、type、text 等字段）和资源文件名中提取示例内容的名称，再扫描核心代码文件：核心不能引用 starter 路径，也不能出现这些名称。还可以在 `content_terms` 中补充名称（`gre.py paths --content-term <名称>`）。
- 确有必要的例外写进 `decoupling_allow`（path、term、reason），没有理由的例外不生效。
- 这条规则针对“核心依赖示例内容”这一类失败；它是文本检查，不能证明核心没有以其他方式写死玩法，后者仍由独立复用验收发现。

### 3.2 创作者工具包（`gre.py kit --item <id> --path ...`，或 `--na "<原因>"`）
| 项 | 内容 |
|---|---|
| start_here | 唯一的创作者快速开始（必需） |
| scene_design_template · camera_window_rules · scene_geometry_contract | 场景设计模板、可见窗口与相机规则、场景与逻辑几何契约 |
| character_spec · layer_rules · animation_import · ui_theme | 角色尺寸/锚点/挂点、图层与遮挡组织、动画与图集导入、UI 布局与主题替换 |
| new_pack_tool · asset_validator | 新建内容包的工具、资源完整性校验器（必需，且必须在首次使用门禁中实际运行） |
| runnable_example | 可运行的示例内容（必需） |
| concept_to_runtime | 概念图、设计、资源生产与接入的关系（游戏需要概念图时） |

只交付适合目标游戏的材料；不适用的项写明原因。契约的数值来自目标游戏研究（[PRESENTATION_2D 5.8](PRESENTATION_2D.md)），Skill 不规定像素常量或美术方法。

### 3.3 干净首次使用门禁（`FIRST_USE.json`，`gre.py first-use check|run`）
`first-use run` 把**已提交的 HEAD** 克隆到全新临时目录（不带缓存、构建产物和本地状态，常见包管理器缓存重定向到临时目录），严格按 start_here 文档逐步执行：

| 步骤 kind | 做什么 |
|---|---|
| create_content_pack | 用工具新建一个内容包 |
| import_assets · validate_assets | 导入资源并用校验器检查 |
| build · launch_runtime · playtest | 构建、启动、按正常输入试玩 |
| negative_missing_resource | 删除必需资源（`remove`），校验或构建**必须失败** |
| regression | 回归测试 |

- 每一步的命令必须原样出现在 start_here 中；`{python}` 表示当前 Python；平台差异用 `argv_windows` / `argv_posix`。
- 每步日志保存在 `re/evidence/first-use-<时间>/`；结果绑定提交、核心指纹、Base 版本和步骤哈希。HEAD、核心或步骤变化后需要重跑。
- 工作区有未提交改动时，测试的仍是最后一次提交，并给出提示；核心与 starter 路径的未提交改动会直接阻止创作者等级。

## 4. 独立复用验收（CREATOR_READY）
由一个**没有参与过本 Base 开发**的 Agent（`assign` 历史中没有出现过，independence = independent_reviewer）只读创作者文档完成：
1. `gre.py reuse-trial start --agent <label> --independence independent_reviewer --docs docs/START_HERE.md ...`：记录开始时的核心文件清单。
2. 新建内容，替换背景、角色、动画和 UI，改一项玩法配置，做出可玩切片；不需要研究原版内部资料。
3. `gre.py reuse-trial finish --result PASS|FAIL|BLOCKED --passed-checks <逗号分隔> --evidence <录像> --assets N --steps N --manual "..." --minutes N --unverified "..."`。工具自动统计核心文件改动数。

PASS 的条件：独立的 Agent；核心零改动；八项检查（new_content、replace_background、replace_character、replace_animation、replace_ui、gameplay_config、playable_slice、no_internal_research_needed）全部完成；有切片录像；版本与核心指纹未变。记录资产数、步骤数、人工介入、首次成功耗时和未验证项。

**无法组织独立 Agent 时，如实保持 NOT_RUN 或 BLOCKED**，Base 停在 CREATOR_CANDIDATE，交接中写明“尚未经过独立复用验证”。不能由开发者自己换个名字充当独立验收者。

## 5. 权利（三项独立记录）
| 记录 | 内容 | 谁能通过 |
|---|---|---|
| RE01 | 原作与第三方代码、组件的复用许可评估（REUSE.json） | Agent 可以自审，如实标注独立性 |
| RE03 | 原作素材与具体表达（角色、关卡、文本、音乐等）的使用权 | **只有原作权利人或其授权法务**（`--role rights_holder`，external_approval）。完全没有使用原作素材和具体表达时，可以 NOT_APPLICABLE 并写明依据 |
| RE02 | 用户对公开发布的批准 | **只有用户**（`--role user`，external_approval）；它不能替代 RE01 或 RE03 |

- 技术等级的计算不读取这些记录，它们也不会因为技术测试而自动通过。
- 只有 RE01、RE02 为 PASS，且 RE03 为 PASS 或带依据的 N/A 时，状态才显示“发布权利记录完整”。即使完整，也只表示记录齐全，不是法律意见，剩余风险永远不为零。
- 原版来自可下载游戏、公开仓库或反编译工程，都不代表其代码和美术可以商业使用。研究原件放在被忽略的 `research-private/`，不进入 Base 核心、starter 或发行包。

## 6. 交付（E7）清单
- `gre.py validate --strict-target` 通过（目标等级已达到）；`gre.py report` 生成最新报告。
- `gre.py base freeze` 冻结当前版本（只有 CREATOR_CANDIDATE 或 CREATOR_READY 可以冻结）；之后的改动用 `gre.py base bump` 开新版本。
- 填写 `re/BASE_HANDOFF.md`，包括“后续游戏创作交接”的 7 项具体做法，运行 `gre.py checkpoint` 和 `gre.py handoff`（COMPLETE）。
- `gre.py export` 写出创作交接 `CREATOR_HANDOFF.json`（[创作交接](CREATION_HANDOFF.md)），供 game-creation-polish 使用。
- 创建只包含本任务改动的 Git 提交；未经授权不 push。
