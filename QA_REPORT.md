# 自身测试报告 — game-production 4.1.0 与 game-reverse-engineering 1.2.0

## game-reverse-engineering 1.2.0：Presentation Reconstruction
`python -m unittest discover -s skills/game-reverse-engineering/tests -v`：**39/39 通过**，没有跳过的测试。新增的 `PresentationTest` 共 8 项：

| 场景 | 测试 | 验证内容 |
|---|---|---|
| 只支持资源导入、没有场景装配能力 | `test_asset_import_only_cannot_pass_presentation` | P1–P8 条目都已验证，但没有场景实验时拒绝 PRESENTATION_READY（等级停在 LOGIC_READY）；状态显示门禁 FAIL；`next` 的第一项是表现重建；只有证据、没填调查字段不算完成；未记录原版对照时被指出 |
| 静态场景，缺少动画和事件绑定 | `test_static_scene_without_animation_and_event_binding_is_not_full_presentation` | PX04、PX05 缺失时门禁不通过；PX05 只有截图时被拒（截图证明不了时序）；补齐后通过 |
| 只能复现一套固定画面 | `test_single_fixed_screen_is_not_a_configurable_scene_system` | PX01 只有一份场景配置时被拒 |
| 场景坐标或锚点变化后必须更新证据 | `test_scene_coordinate_or_anchor_change_requires_new_evidence` | 锚点文件改动后 PX02、PX06 过期，原有声明报错；重新测量后通过，旧测量保留在 history 中 |
| 新素材和 UI 主题不大改核心即可运行 | `test_new_assets_and_ui_theme_run_without_core_changes` | 换前与换后素材相同、UI 相同时分别被拒；为某个主题修改核心后，被判定为“换美术需要改核心” |
| 截图不能当作引擎架构事实 | `test_screenshots_alone_cannot_establish_engine_architecture` | 只有截图时不能标 VERIFIED 或 STATIC_ONLY；可以标为 INFERRED，但必须说明缺口 |
| 原版无法运行时如实标注 | `test_missing_dynamic_evidence_is_reported_not_hidden` | 门禁可以通过，但状态和报告都写明“NOT dynamically verified” |
| 不破坏旧项目和既有门禁 | `test_claims_made_before_the_gate_stay_readable` | 1.1.0 规则下的 PRESENTATION_READY 声明、缺少 PRESENTATION.json 时只给出提示、不报错；`upgrade` 只新增文件；v4 的 validate 仍然通过 |

另外：Creator 测试配置必须带场景配置，两套场景相同时被判定无效；交接检查逐项核对“后续游戏创作交接”的 7 项答案。原有的 31 个测试全部继续通过，其中 Creator、权利、交接相关的测试已按新规则补充了场景实验和交接内容。

**变异检查**：用复制目录 + 对照组的方法，对 13 条新规则逐条改坏，对应测试都会失败。这 13 条是：
- 门禁是 PRESENTATION_READY 的必要条件
- PX01 需要两份场景配置
- 布局和锚点文件变化后过期
- 换主题不能改核心
- 换主题必须换素材
- 检查需要特定类型的证据
- 截图不能作为 VERIFIED 的依据
- 截图不能作为 STATIC_ONLY 的依据
- 调查字段必须填写
- 必须记录原版对照
- 无法对照时必须如实报告
- 创作交接必须作答
- Creator 测试配置的场景不能相同

首轮有 3 条未被抓到（换素材、调查字段、原版对照），已补充测试断言后全部抓到。

---

# 自身测试报告 — game-production 4.1.0 与 game-reverse-engineering 1.1.0

- 审查日期：2026-10-19
- 分支：`feature/game-reverse-engineering`（尚未合并到 main）
- 环境：Windows 10.0.26200，Python 3.12.10。代码只用 Python 3.9 可用的语法和标准库，但没有在 3.9、macOS 或 Linux 上实际运行过。
- 独立性：self_review（同一个 Agent 编写并测试），没有独立审查者。

## game-reverse-engineering 1.1.0
`python -m unittest discover -s skills/game-reverse-engineering/tests -v`：**31/31 通过**，没有跳过的测试。

### 1.1.0 新增的验收场景
| 场景 | 测试 | 验证内容 |
|---|---|---|
| 发现模板之外的游戏独特能力 | `test_game_specific_capability_beyond_the_template` | 发现的条目必须附发现位置的证据；新条目会阻断 LOGIC_READY，原有声明被判定超出证据；验证后恢复；UNAVAILABLE 必须写原因 |
| 范围与排除需要理由 | `test_scope_changes_and_exclusions_need_reasons` | 排除或降级模板条目必须写 scope_reason；排除项不阻断等级 |
| 视觉配置不同，但可以共用通用资源 | `test_visual_configs_may_share_common_resources_but_not_most_visuals` | 公共字体放在 shared_files 中合法共用；视觉资产重合 20% 通过，40% 被拒 |
| 只换图片、没有玩法改造 | `test_image_swap_without_gameplay_change_is_not_production_capability` | 没有玩法改动时拒绝 Creator Ready，状态标为 visual-only；只改表现条目的“玩法改动”被拒；用 debug 输入跑的循环被拒 |
| 原版行为未知时允许 EXTENSION、不允许 PARITY | `test_unknown_original_allows_extension_but_never_parity` | UNKNOWN 或 INFERRED 的条目标为 PARITY 被拒；未显式标为 EXTENSION 时不能实现；REPLACEMENT 必须写差异；报告分别统计三类 |
| 核心代码变更后旧 QA 失效 | `test_core_change_invalidates_related_qa`、`test_creator_ready_…` | 改动核心后等级降为 NONE，声明报错，条目标为 stale；用 code_paths 限定在无关目录的条目不受影响；改动核心后旧的 Creator 测试配置失效 |
| 高优先级缺口长期未完成时不能只做打磨 | `test_high_priority_gap_blocks_endless_polish_and_research` | 连续第 5 个打磨任务被拒（POLISH_BLOCKED），`next` 的第一项是阻断等级的核心缺口；写明理由可以覆盖；研究预算用完后再研究被拒，并建议改用成熟组件 |
| 长任务超时后的安全恢复 | `test_long_task_timeout_is_recovered_safely` | 未超时的任务不能 recover；超时后 STALLED；recover restart 记为 TIMED_OUT、计入失败、只提示结束记录的 pid；abandon 后交接检查不再报 ACTIVE |
| 旧状态可读、升级只做加法 | `test_records_from_1_0_0_stay_readable_and_upgrade_is_additive` | 1.0.0 格式（无 discovery、无 RE03、无新字段、旧规则下的等级声明）可以校验通过，只给出提示；upgrade 后已有条目内容不变 |
| 权利三项独立 | `test_rights_are_separate_and_user_approval_does_not_replace_rights_holder` | 用户的批准不能通过 RE03；RE02 不能自审；记录状态始终注明“剩余风险不为零”；技术等级不受影响 |
| 测试素材不得来自隔离材料 | `test_probe_content_must_not_come_from_quarantined_research` | 来自 QUARANTINE 路径的资产被拒 |
| 执行边界 | `test_legally_reusable_code_path`、`test_code_that_cannot_be_legally_reused` | reviewed/sandboxed 必须写说明；隔离材料不能是 reviewed |

### 保留的 1.0.0 场景（全部继续通过）
空项目启动、已有项目接管、代码可合法复用、代码不能合法复用、无法动态运行原作、逻辑完成但表现未完成、表现域不能整体跳过、两套测试配置、中断后恢复、不同 Agent 接续、v4 项目迁移（v4 记录字节不变，v4 与本 Skill 的 validate 都通过）、v3 项目被拒、模板与 v4 一致、证据不覆盖、历史删改被发现、Base 升版本后重新验证、报告另存、CRLF 安装、CLI。

### 变异检查（更正）
方法：把整个 Skill 目录复制到临时位置，只把副本中的一条规则改为失效，为副本重新生成清单，然后在副本中运行对应的测试；同时运行一个不做修改的对照组，它必须通过。

结果：对照组通过，以下 11 条规则改坏后，对应测试都会失败。
- 玩法改动是必需的
- 原版行为未知时禁止 PARITY
- 代码指纹过期
- 阻止连续打磨
- RE03 必须由权利人批准
- 视觉资产重合上限
- 必须完成特有能力发现
- 表现条目必须有运行时证据
- 测试配置的核心指纹
- 隔离模块不可复用
- RE02/RE03 批准必须来自外部（不可自审）

“测试配置的核心指纹”最初没有被抓到，已补充断言。

**更正**：1.0.0 报告中写的“4 项变异检查通过”用的是另一种方法。该方法在临时位置加载工具副本，但副本中读取清单的函数仍指向原路径，结果测试都在初始化阶段就出错，而不是因为抓到了变异，因此那次结论无效。本次已用上面的方法重新验证，并覆盖了那 4 条规则。

## game-production 4.1.0
`python -m unittest discover -s tests -v`：**32/32 通过**（本次未修改 game-production 的代码）。

## 其他检查
- README 中的四段启动提示词与对应的提示词文件逐字一致。
- 仓库内所有相对 Markdown 链接都指向存在的文件。
- 两份 SHA256SUMS（根目录、`skills/game-reverse-engineering/`）与实际文件一致。
- 扫描私钥、令牌和密码赋值：无命中。经验文档只引用各项目内的相对路径。

## 已知限制
- 31 个测试在本机运行约 3 分钟。耗时主要在带缩进的 JSON 读写，单条命令的实际使用影响很小（每次保存约 0.07 秒）。
- 工具不运行原作，不调用反编译器，不生成美术，不做法律判断。本报告不代表任何一款 Base 或游戏已经达到相应等级。
