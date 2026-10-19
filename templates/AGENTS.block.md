<!-- GAME_PRODUCTION_V4_BEGIN -->
## Game Production workflow (v4)
使用 `.agents/skills/game-production/SKILL.md`：研究一次 → 可复用 Base → `games/<id>/` 下逐款策划、美术策划、开发、美术、QA、打包。任意 Agent 可接续，不绑定软件身份。
先读 `.production/WORKSPACE.json`（当前 Base / Game / 阶段 / 授权范围）与 `.production/HANDOFF.md`；处理某款游戏时再读 `games/<id>/.production/` 与 `design/`。不要把一款游戏的资产、数值或 QA 状态写进另一款。
在授权范围内无人值守推进：实现→测试→检查→返工→检查点→下一项。阶段完成不是停止点；达到授权目标或真实外部阻断才交接。无人值守不等于扩大目标。
保留已有成果，不擅自重写 Base 或降低标准；修改 Base 要做依赖游戏回归。本机路径和能力在忽略目录 `.production/local/`。
未验证就写未验证。BASE_READY ≠ GAME_READY ≠ 公开发布批准。默认不 push、不付费、不公开部署、不修改生产或无关项目。
此引导不覆盖更高优先级规则或用户明确限制；发生冲突先按更严格且适用的权限执行。
<!-- GAME_PRODUCTION_V4_END -->
