---
name: game-creation-polish
description: 预览版（未完成）。在 game-reverse-engineering 交付的 Creator Base 上制作和打磨具体游戏：每个游戏在 games/<id>/ 中独立完成策划、美术与资源、内容开发、实机 QA 返工和发行候选准备，并通过 CREATOR_HANDOFF.json 读取 Base 的等级、保真度和权利状态。不做逆向研究，不修改 Base 核心。
metadata:
  version: "0.1.0-preview"
  status: "PREVIEW"
  language: "zh-CN"
  upstream: "game-reverse-engineering >= 2.0.0（creator-handoff-1）"
---
# Game Creation & Polish · v0.1.0-preview — 在 Creator Base 上做游戏

> **状态：PREVIEW（未完成）。** 已实现的是游戏记录、阶段与门禁、Base 交接校验、范围与恢复工具；美术生产、实机 QA 和打包流程只有规则与记录格式，没有端到端验证过的自动化。见第 7 节。

## 1. 职责
- **输入**：一个已在工作区中的 Base，以及它的最新创作交接 `.production/bases/<id>/handoff/<version>/*-CREATOR_HANDOFF.json`（由 game-reverse-engineering 的 `gre.py export` 生成，[契约](references/HANDOFF_CONTRACT.md)）。
- **输出**：`games/<id>/` 下独立的游戏：策划、美术与资源、内容、QA 证据、发行候选包和交接记录。
- **不负责**：研究原版、建设或验收 Base、修改 Base 核心/starter/工具包。Base 不够用时把需求回报上游（`core_extensions.proposed_for_base`、`retrospective.core_feedback`）。

## 2. 每次进入项目
1. `python <skill>/scripts/gcp.py status --project <root>`：看 Base 交接等级、机制/视觉保真度、独立复用状态，以及各游戏的阶段和下一步。不依赖旧聊天。
2. 读 Base 的 START_HERE 与 BASE_HANDOFF、焦点游戏的 GAME.json、BACKLOG、HANDOFF。
3. 检查 Git 状态和未提交改动，不覆盖别人的修改。换设备时运行 `gcp.py env`（只写本地文件）。
4. 交接缺失、被改动或低于 CREATOR_CANDIDATE：可以先做 G1/G2 策划，但不能让游戏达到 GAME_READY；把问题交回 game-reverse-engineering。

## 3. 阶段与门禁
G0 建游戏 → G1 策划（D01）→ G2 美术策划与代表资产（D02）→ G3 内容开发（Q01–Q02）→ G4 资产制作与集成 → G5 QA 与返工（Q03–Q08，GAME_READY）→ G6 发行候选（R01–R02）→ G7 复盘与下一款。权利审查 R03、公开发布批准 R04 单独记录。阶段非瀑布，有效证据可复用，缺口只回退受影响部分。详见 [阶段](references/STAGES.md) 与 [质量门禁](references/QUALITY.md)。

| 游戏就绪度 | 要求 |
|---|---|
| FEATURE_COMPLETE | D01、Q01、Q02 |
| GAME_READY | + D02、Q03–Q08；Base 交接完整且 ≥ CREATOR_CANDIDATE |
| RELEASE_CANDIDATE | + R01、R02；产物路径与哈希一致 |
| PUBLICATION_APPROVED | + R03、R04（external_approval）；交接中 RE01 PASS、RE03 PASS/N/A |

## 4. 硬规则
- 只写当前游戏目录；不修改交接中列出的 Base 核心、starter 和工具包文件。交接文件哈希或核心指纹变化后，游戏不能达到 GAME_READY。
- 新美术必须遵守 Base 的场景几何契约、角色规范、图层规则和动画导入规则，导入前用 Base 的资产校验器检查；不得用逐个“调像素”掩盖违反契约。
- 占位资源、程序生成的临时图和原版素材不得作为正式资产交付；资产状态从 planned 到 verified 逐级记录来源与许可（[资产管线](references/ASSET_PIPELINE.md)）。
- 没做过的验证写 UNVERIFIED；同一个 Agent 换角色审查仍是 self_review；R04 只能来自用户或权利人。
- 不因为原版来自可下载游戏、公开仓库或反编译工程，就默认其代码和美术可以商业使用。发行包不得包含研究原件、密钥或本机路径。

## 5. 无人值守、范围与接力
在授权范围（`scope`：game / batch / full_pipeline）内持续推进，直到目标的证据满足或遇到真实外部阻断；不自行扩大范围，不空转。停止状态、预算、Git 基线、跨 Agent/会话/设备接力和状态文件见 [执行与接力](references/OPERATIONS.md)。

## 6. 工具
```text
gcp.py init --project <root>                        # 安装到 .agents/skills/game-creation-polish（工作区和 Base 必须已存在）
gcp.py game create --project <root> --id game-01 --base core@1.0.0 --user-request "<用户原话>"
gcp.py game stage  --project <root> --id game-01 --stage G1 --status DONE
gcp.py game update --project <root> --id game-01 --readiness GAME_READY | --artifact <path> | --assign-agent <label> --assign-stages G2
gcp.py game rebind --project <root> --id game-01 --base core@1.1.0
gcp.py scope --project <root> --target game|batch|full_pipeline --basis "<用户原话>" [--game-quota 3]
gcp.py focus|run|env|status|validate|handoff --project <root> ...
```
工具只维护记录和校验证据哈希、就绪度声明、交接完整性与路径隔离；不运行游戏、不判断画面或玩法品质、不做法律判断。

## 7. 尚未实现 / 未验证
- 没有在真实游戏项目上完成过端到端的 G0–G6 流程；规则来自上一代工作流和逆向 Skill 的经验，未经本 Skill 独立验证。
- 不自动生成美术、不调用生图服务、不运行浏览器 QA、不打包，只记录这些步骤的结果与证据。
- 不验证创作交接的来源签名；能写工作区的人可以伪造交接。
- 不自动把 Base 改进需求转交给 game-reverse-engineering。

## 8. 参考文档
[交接契约](references/HANDOFF_CONTRACT.md) · [阶段](references/STAGES.md) · [质量门禁](references/QUALITY.md) · [执行与接力](references/OPERATIONS.md) · [策划规范](references/GAME_DESIGN_GUIDE.md) · [美术策划](references/ART_DIRECTION_GUIDE.md) · [资产管线](references/ASSET_PIPELINE.md) · [品类检查](references/GENRE_CHECKS.md) · [安装兼容性](references/OFFICIAL_SOURCES.md)

启动提示词：[在 Base 上开始新游戏](prompts/START.md) · [接续已有游戏](prompts/CONTINUE.md)
