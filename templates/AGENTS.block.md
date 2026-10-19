<!-- GAME_PRODUCTION_V3_BEGIN -->
## Game Production workflow
使用 `.agents/skills/game-production/SKILL.md` 的阶段式流程；任意 Agent 可接续，不绑定软件身份。
项目目标/状态在 `.production/`。先读 PROJECT、STATE、BACKLOG、GATES、HANDOFF，再核验当前代码和环境。
在授权范围内无人值守推进：实现→测试→检查→返工→检查点→下一项。普通里程碑不等于结束；真实阻断或目标达到才交接。
保留已有成果，不擅自重写核心或降低标准。多设备默认单写入者；本机路径和能力在忽略目录 `.production/local/`。
不根据报告自动放行；未验证就写未验证。默认不 push、不付费、不公开部署、不修改生产或无关项目。
此引导不覆盖更高优先级规则或用户明确限制；发生冲突先按更严格且适用的权限执行。
<!-- GAME_PRODUCTION_V3_END -->
