# 本游戏任务池
只记录本游戏的任务；Base 改动写到工作区 `.production/BACKLOG.md` 并注明受影响游戏。状态 TODO / ACTIVE / BLOCKED / DONE。

| ID | 阶段 | 优先级 | 任务和预期产物 | 依赖 | 状态 | 归属/允许改动范围 | 验收与证据 |
|---|---|---|---|---|---|---|---|
| T-001 | G1 | P0 | 根据需求与 Base 能力编写 design/GAME_DESIGN.md | Base 能力清单 | TODO | 本游戏 design/ | D01 |
| T-002 | G2 | P0 | 美术方向、资产计划、动画规格 + 一个代表资产全链路试制 | T-001 | TODO | 本游戏 design/、assets/ | D02 |

完成一项后自动选择下一未阻断任务。某项 BLOCKED 不等于本游戏应停止。
