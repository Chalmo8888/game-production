<!-- GAME_REVERSE_ENGINEERING_V1_BEGIN -->
## Game Reverse Engineering workflow
研究参考游戏并建设可复用 2D Creator Base 时，使用 `.agents/skills/game-reverse-engineering/SKILL.md`。任意 Agent 可接续，不绑定软件身份。
先运行 `python .agents/skills/game-reverse-engineering/scripts/gre.py resume --project .`，再读 `.production/bases/<id>/re/`（RE_STATE、PARITY、REUSE、PRESENTATION、PROBES、CREATOR_KIT、FIRST_USE、REUSE_TRIAL、BASE_HANDOFF）。
能力等价矩阵是验收核心：只有带测试/运行时/测量证据的 VERIFIED 才算完成。LOGIC_READY ≠ PRESENTATION_READY ≠ CREATOR_CANDIDATE ≠ CREATOR_READY；权利另行记录。
原版管线优先：先研究原版怎样画出画面，再决定 Base 怎样做；每个调查项写 A/B/C/D，方法不同就写差异、原因、影响；机制保真与视觉保真分开，占位图与自有美术不是原版证据。
核心不依赖示例内容；创作者工具包与 START_HERE 要能通过干净首次使用门禁；独立复用验收无法组织时如实停在 CREATOR_CANDIDATE。交付用 `gre.py export`。
在授权范围内无人值守推进；不覆盖历史证据；会话中断时保存检查点。默认不 push、不付费、不公开部署、不执行不可信脚本、不提交研究原件。
<!-- GAME_REVERSE_ENGINEERING_V1_END -->
