# Base 验收规则

## 1. 三个交付等级（互不替代）
| 等级 | 含义 | 条件（工具核对） |
|---|---|---|
| LOGIC_READY | 玩法逻辑可以作为成熟基础使用 | RE01 PASS（复用评估完成，无 REVIEW）；L1–L6 全部条目 VERIFIED 或带依据 N/A；L1、L2、L5、L6 各至少一个 VERIFIED |
| PRESENTATION_READY | 2D 表现体系完整可用 | + P1–P8 全部满足，每个域至少一个 VERIFIED，表现证据为运行时录制或测量 |
| CREATOR_READY | 只换配置和资产就能做出不同的游戏 | + C1 全部满足；两套有效的原创测试配置；核心能力 `reusable_for_new_games = true` |

- Logic Ready 不等于 Presentation Ready，Presentation Ready 不等于 Creator Ready。
- 所有 VERIFIED 都必须绑定当前 Base 版本。Base 升级后，等级需要重新验证（旧等级的声明会给出警告）。
- 等级只能用 `gre.py level --set` 声明，证据不足时会被拒绝；手动改写声明会被 `validate` 发现。
- 不需要制作正式的 Game 01，也不需要商业级美术。

## 2. Creator 验证（两套原创测试配置）
每套测试配置（`gre.py probe`）记录：
- **配置文件和资产文件**（自动计算 SHA-256），必须放在 `core_paths` 之外。
- **五类替换的运行时证据**：角色（character）、动画（animation）、单位（unit）、地图（map）、视觉风格（visual_style）。
- **核心指纹**：对 core_paths 下全部文件（路径 + 内容）计算的哈希。
- 许可（原创测试内容），以及 `core_changes_needed`（必须为空）。

有效的条件：
1. 两套配置都针对当前 Base 版本录制，文件存在且哈希一致。
2. **差异明显**：两套之间没有相同的配置文件或资产文件（按哈希比较），每类替换的证据也各不相同。复制一套再改名不算。
3. **核心不变**：两套配置记录的核心指纹都等于当前核心的指纹。如果为了某一套配置修改了核心，指纹会改变，两套配置都要在新核心上重新录制；需要改核心的，应把改动并入 Base、升版本后重跑。
4. 证据类型为运行时录制、测量或测试。

建议两套配置在类型、比例、调色、动画方式（例如一套逐帧、一套拆件）和地图结构上都有明显差异，用来证明扩展点确实通用。

## 3. 权利（独立门禁）
| 记录 | 内容 | 谁能通过 |
|---|---|---|
| RE01 | 复用与授权评估完成 | Agent 可以自审（如实标注独立性） |
| v4 Base B02 | 代码来源审查 | 按 v4 规则；它是 v4 COMMERCIAL_BASE_CANDIDATE 的前提 |
| RE02 | 商业发行许可 | **只接受用户、权利人或其授权法务的 external_approval**，并附批准记录 |

技术等级的计算不读取 B02 和 RE02，B02 和 RE02 也不会因为技术测试而自动通过。`status` 和报告会把权利状态单独列出。

## 4. 交付（E7）清单
- `gre.py validate --strict-target` 通过（目标等级已达到）。
- `gre.py report` 生成最新报告。
- 冻结 Base 版本（v4：`project.py base update --freeze`），并按报告把证据映射到 v4 门禁 B01、B03–B08（见 V4_INTEGRATION）。
- 填写 `re/BASE_HANDOFF.md`，运行 `gre.py checkpoint` 和 `gre.py handoff`（COMPLETE）。
- 创建只包含本任务改动的 Git 提交；未经授权不 push。
