# 与 game-production v4 的关系与迁移

## 1. 分工
- **game-reverse-engineering（本 Skill）**：深度执行 v4 的 R0–R2（研究、复用判断、Base 建设），交付等级为 LOGIC / PRESENTATION / CREATOR_READY。
- **game-production v4**：工作区、Base 版本、游戏（`games/<id>/`）、授权范围、三层门禁和交接机制。后续的 `game-creation-polish` Skill 将负责基于 Base 做游戏。
- 两者共用同一个 v4 工作区格式（schema 3.0）。本 Skill 的记录放在 `.production/bases/<id>/re/`，不修改 v4 的 Base 记录和游戏记录。

## 2. 三种起点
| 起点 | 命令 | 结果 |
|---|---|---|
| 空文件夹 | `gre.py init --project . --code-path engine --core-path engine/core --reference <url>` | 创建 v4 兼容工作区（范围：只做 Base，game_quota = 0）、Base 记录和 re/ 记录 |
| 已有工程（没有任何记录） | `gre.py init --project . --code-path . --core-path src/engine` | 登记已有代码为 Base（intake = adopt_existing），不改动任何代码 |
| 已有 v4 工作区 | `gre.py init --project . --base-id core --core-path engine/core` | 接管已有 Base，只新增 re/ 记录；v4 文件保持字节不变，游戏不受影响 |
| v3 单游戏项目 | 先运行 game-production `project.py migrate`，再执行上一行 | v3 的任务和证据保持不变 |

## 3. 等级与 v4 门禁的对应
本 Skill 的等级不会自动写入 v4 门禁。达到目标等级后，用 `gre.py report` 生成报告，作为证据更新 v4 的 Base 门禁，再用 v4 工具声明 BASE_READY：
| v4 门禁 | 证据来源 |
|---|---|
| B01 研究与机制证据 | PARITY 中的原版证据等级与 dynamic_gap（报告） |
| B02 代码来源与权利 | REUSE.json + RE01 审查记录（法律结论仍需外部确认）；原作素材与具体表达另见 RE03，用户发布批准另见 RE02，三者不能互相替代 |
| B03 核心机制实现 | LOGIC_READY 条目的验证证据 |
| B04 数据配置与内容扩展接口 | C1 条目 + 两套 Creator 测试配置 |
| B05 资源与动画接口 | P1/P2/P3/P6 条目的运行时证据 |
| B06 构建与自动测试 | Base 构建和测试日志 |
| B07 示例内容可运行 | Creator 测试配置的运行时证据 |
| B08 兼容与依赖回归 | 新版本时对依赖游戏的回归；首个版本可以 N/A |

v4 门禁的 PASS 需要写 `base_version`；本 Skill 的验证同样绑定 Base 版本，两边应保持一致。

## 4. Base 升级
用 v4 工具 `project.py base bump` 开新版本后，本 Skill 中旧版本的 VERIFIED 不再计入等级，需要针对新版本重新验证并重跑 Creator 测试配置；v4 会列出需要回归的游戏。

## 5. 从 game-reverse-engineering 1.0.0 升级
1.1.0 只做加法，数据格式仍是 `gre-1.0`：
- 旧记录可以直接读取；缺少的新字段（scope、capability_class、code_paths、discovery、RE03）按保守规则推导，并给出提示。
- 在 1.0.0 规则下做出的等级声明，如果不满足 1.1.0 的新规则（例如尚未完成特有能力发现），只给出提示，不会报错。
- 运行 `gre.py upgrade` 会补充缺少的 RE03、discovery、`max_visual_overlap` 和新的防护阈值，不修改任何已有值。
- 1.0.0 中 RE02 的含义是“商业发行许可”，1.1.0 拆成两项：RE02（用户公开发布批准）和 RE03（原作权利人授权）。旧的 RE02 PASS 没有 role 时会给出提示，请按实际情况补充或改到 RE03。
- 旧的 Creator 测试配置缺少玩法改动和完整循环，在补齐之前不能证明 Creator Ready。

## 6. 兼容性保证（有测试覆盖）
- 在 v4 工作区上运行 `gre.py init` 时，v4 的工作区、Base、游戏记录保持字节不变，`project.py validate` 仍然通过。
- 本 Skill 创建的工作区可以直接通过 v4 的 `project.py validate`。
- 本 Skill 自带的 v4 模板与 game-production 的模板保持一致（仓库内有测试检查）。
- 根目录的 v4 入口（`prompts/START_RESEARCH.md` 等）继续有效，并指向本 Skill。
