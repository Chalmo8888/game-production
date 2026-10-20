# 接续一款未完成的游戏（跨会话 / 跨设备 / 换 Agent）

```text
请使用 Game Creation & Polish Skill，继续完成游戏【game-id，留空表示 WORKSPACE 中的焦点游戏】。

读取 .agents/skills/game-creation-polish/SKILL.md、.production/WORKSPACE.json，
以及 games/<id>/.production/ 下的 GAME.json、GATES.json、ASSETS.json、BACKLOG.md、HANDOFF.md
和 games/<id>/design/。按文件恢复进度，不依赖旧聊天记录。

1. 运行 gcp.py status --game <id> 和 validate --game <id>：确认阶段、就绪度声明与证据是否一致、
   绑定的 Base 版本及其创作交接是否仍完整、assignment 和下一步。
2. 检查 Git 状态和未提交改动，不覆盖别人的修改；确认上一位写入者已经交接。
   换了设备时运行 gcp.py env --device-label <名称>，做最小构建和冒烟测试后再继续。
3. 绑定的 Base 有新版本时，先判断是否改绑；改绑后必须回归，不能沿用旧 QA 结论。
4. gcp.py focus --game <id>，从最高优先级且未被阻断的任务继续；证据仍有效的阶段不重做，
   NEEDS_REWORK 的阶段优先返工。
5. 只修改本游戏的目录；Base 问题记录到 core_extensions.proposed_for_base 并回报。

授权范围：推进到 run.scope.required_readiness（默认 RELEASE_CANDIDATE）。
【如只做部分阶段，写明：本次只做 G3–G5】

【无人值守执行规则】
开始执行，直到达到当前目标可验证的交付要求，或遇到无法自行解决的真实外部阻断。
在授权和预算范围内仍有有价值且可执行的工作，就继续；普通技术决策自行处理。
质量不达标必须自主返工；一个任务受阻，继续其他工作。不空转、不虚假汇报。
会话终止时保存真实检查点，不声称仍在后台执行。无人值守不意味着扩大目标。

每个实质里程碑更新 GAME.json、GATES、BACKLOG 和 HANDOFF，结束前运行 handoff --game <id> --check，
并创建只包含本任务改动的本地提交。未经明确授权，不 push、不公开部署、不付费、不删除无关文件。
现在开始实际工作。
```
