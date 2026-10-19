<!-- GAME_REVERSE_ENGINEERING_V1_BEGIN -->
## Game Reverse Engineering workflow
研究参考游戏并建设可复用 2D Base 时，使用 `.agents/skills/game-reverse-engineering/SKILL.md`。任意 Agent 可接续，不绑定软件身份。
先运行 `python .agents/skills/game-reverse-engineering/scripts/gre.py resume --project .`，再读 `.production/bases/<id>/re/`（RE_STATE、PARITY、REUSE、PROBES、BASE_HANDOFF）。
能力等价矩阵是验收核心：只有带测试/运行时/测量证据的 VERIFIED 才算完成；接口或文档不算。Logic Ready ≠ Presentation Ready ≠ Creator Ready；商业许可另设门禁。
模板 38 项只是起点：要发现游戏特有能力；如实标注 PARITY / REPLACEMENT / EXTENSION。每轮用 `gre.py next` 选价值最高的缺口。
在授权范围内无人值守推进，研究只服务于矩阵中的缺口；不覆盖历史证据；会话中断时保存检查点。默认不 push、不付费、不公开部署、不执行不可信脚本、不提交研究原件。
<!-- GAME_REVERSE_ENGINEERING_V1_END -->
