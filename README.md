# Game Production Skill v3.0.0
## 按阶段生产 · 不绑定 Agent · 可无人值守接续

这是一套跨软件、跨设备的游戏生产 Skill。单个 Agent 可做完整流程，也可多软件按阶段接力；不再指定 Cursor 开发、Codex 美术。

**三层结构：Skill 规定工作方法；每个游戏的 `.production/` 保存目标与真实进度；当前设备的本地配置记录工具、路径与能力。**

## 最简单的操作

把本文件夹 `game-production` 放入游戏工程的：

```text
<游戏根目录>/.agents/skills/game-production/
```

然后在任何能够读项目并执行开发工具的 Agent 中发送：

```text
读取 .agents/skills/game-production/SKILL.md 和 .agents/skills/game-production/prompts/START.md。
这是已有项目，先检查现有代码、文档和证据，初始化或恢复 .production/。
按当前项目目标使用 auto 模式，不重建工程，不指定软件分工。
开始调查并执行；只要执行环境允许、在授权预算内且仍有有价值的工作可推进，就持续开发、测试、检查、返工和扩展。达到可验证交付要求或真实外部阻断才停止；普通里程碑后自动继续。
```

其中 `prompts/START.md` 指 Skill 目录下的文件；Agent 应解析实际路径。不需要使用软件专属斜杠命令。

## 自动安装与状态初始化（可让 Agent 执行）

从解压目录执行，或已放入项目后从该 Skill 目录执行：

```text
python <本包目录>/scripts/project.py init --project "<游戏根目录>"
```

Windows 示例：

```powershell
python "D:\skills\game-production\scripts\project.py" init --project "E:\games\my-game"
```

命令仅复制本 Skill 并新增缺少的流程记录；不会重新生成游戏，不会覆盖已有进度、Git 改动或 AGENTS 内容。已有不同版本 Skill 同路径时拒绝自动覆盖，请按迁移手册处理。Python 缺失时 Agent 可按模板保守手动安装，不必重置系统环境。

初始化后 Agent 需要依据现有资料填写/复核项目目标、交付合同与门禁标准；模板并不代表游戏已通过验收。

## 常用方式

| 需求 | 入口 | 行为 |
|---|---|---|
| 一次授权做全程 | `prompts/START.md` | auto；达阶段出口就继续 |
| 已有游戏直接完善 | `prompts/ADOPT_EXISTING.md` | 继承成果，定位缺口，不从零重写 |
| 只让这台做美术 | `prompts/STAGE.md`，指定 S4 | 阶段内无人值守，结束交接而非全项目完成 |
| 换设备/换软件 | `prompts/RESUME.md` | 核对快照和能力，接上次任务 |
| 审查而不改 | `prompts/REVIEW.md` | 独立证据与缺陷报告；默认只读 |
| 暂停并交出 | `prompts/HANDOFF.md` | 保存可恢复状态和同步清单 |

## 阶段
S0 接管与路线 → 按需 S1 研究 → S2 实现与内容 ↔ S3 资产合同 → S4 资产制作与集成 → S5 综合验收/返工 → S6 候选打包与交接。

不是要求每款游戏从头走一遍。代码已有就进入未完成项；不做正式美术的任务交付机制与管线包；用户要游戏时不擅自扩成通用 Creator Base。质量检查贯穿全流程。

## 跨设备怎么用
建议一个游戏一个独立仓库（可按需设为私有），项目内固定一份 Skill 版本。同步游戏代码、允许共享的资源、合同与 `.production/` 记录；**只同步 Skill 不能接续游戏。**

默认单写入者交接：设备 A 保存并停止写 → 同步经检查的项目 → 设备 B 重新探测环境、核对资源、构建冒烟 → RESUME。私有 push 需对指定仓库/分支预授权，不自动公开部署。

`.production/local/` 不同步，不放凭据到共享状态。缓存、虚拟环境、编译器安装和本机端口不直接复制到另一 OS；大资产需单独核对哈希与是否已同步。并行见 `references/CROSS_DEVICE.md`。

## 质量与停止规则
未验证不是通过；模式能启动不是能通关；1 个成功种子不是平衡；图集存在不是动作自然；可打 ZIP 不是平台已接受；工程来源审计不是法务授权。

无人值守需要在目标、权限、预算内持续做有价值的工作。若只有外部授权/工具/真人验证仍缺，交付候选和阻断。达到目标后结束，不无限扩展。宿主停止后本包不会自行唤醒 Agent，也不承诺固定工作 8/14 小时。

## 辅助检查

```text
python <skill-root>/scripts/project.py validate --project <game-root>
python <skill-root>/scripts/project.py validate --project <game-root> --strict-target
python <skill-root>/scripts/project.py handoff --project <game-root>
python -m unittest discover -s <skill-root>/tests -v
```

普通 validate 检查状态结构、PASS 的证据路径和 SHA-256。strict-target 还要求已定义验收合同、适用交付门禁通过。**两者都不实际玩游戏，不自动判定“商业可发布”。**

## 上传到自己的 GitHub 仓库（例如 `Chalmo8888/game-production`）

推荐直接以本目录内容作为仓库根目录，让 GitHub 首页显示 `README.md` 与 `SKILL.md`，而不是只上传 ZIP 或多嵌套一层目录。

- 公共仓库（Public）：适合公开复用的通用规则与样例，上传前核对许可证、第三方引用和任何敏感资料；默认没有自动授予他人的使用许可，若想允许复用需单独选择适当许可证。
- 私有仓库（Private）：适合暂时仅自己多设备使用，仍需谨慎管理 Token、密钥和项目原件。
- 本仓库只存 Skill、模板与可公开工具；具体游戏源码、逆向原件、账号信息、商用来源审查资料各放对应项目的受控空间。
- 新建游戏工程时固定 Skill 的某个版本；旧项目更新前阅读 `references/MIGRATION_V2.md`，不要热更新无人值守中的任务。

## 目录

```text
game-production/
  SKILL.md                 核心调度规则，按需读阶段细则
  README.md                人的操作入口
  prompts/                 工具无关的启动/阶段/接续/审查/交接提示词
  references/              阶段、无人值守、质量、资源、来源、跨设备规则
  templates/               本项目状态与按需文档模板
  scripts/project.py       安全初始化、状态校验、接续摘要
  tests/                   辅助脚本测试
  QA_REPORT.md             本包自身验证范围，不是你的游戏验收
```

从旧版 v2 升级先读 `references/MIGRATION_V2.md`，从 v1 升级先读 `references/MIGRATION_V1.md`。客户端自动发现位置的依据见 `references/OFFICIAL_SOURCES.md`。安装方式按官方文件核对过；不等于已经在你的所有设备和软件版本实测。
