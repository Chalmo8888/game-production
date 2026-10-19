# 继续一款未完成的游戏

适用场景：某款游戏已经在 `games/<id>/` 中开发到一半，你希望当前 Agent（同一个或另一个）接着做完。

```text
请按照当前项目中的 Game Production Skill，继续完成游戏【game-id，留空表示 WORKSPACE 中的焦点游戏】。

请读取 .agents/skills/game-production/SKILL.md、.production/WORKSPACE.json、.production/HANDOFF.md，
以及 games/<id>/.production/ 下的 GAME.json、GATES.json、ASSETS.json、BACKLOG.md、HANDOFF.md
和 games/<id>/design/。按文件恢复进度，不依赖旧聊天记录。

1. 运行 project.py status --game <id> 和 validate，确认当前阶段、就绪度声明与证据是否一致、
   绑定的 Base 版本、assignment 和下一步。
2. 检查 Git 状态和未提交的改动，不覆盖别人的修改。确认上一位写入者已经交接。
3. 绑定的 Base 已有新版本时，先判断是否需要改绑；改绑必须做回归，不能直接沿用旧的 QA 结论。
4. 用 project.py focus --game <id> 切换焦点，从最高优先级且未被阻断的任务继续。已经验证、
   证据仍然有效的阶段不重做；NEEDS_REWORK 的阶段优先返工。
5. 只修改本游戏的目录。需要改 Base 时走升版本与依赖回归的流程。

授权范围：把这款游戏推进到 WORKSPACE 中 run.scope.required_readiness 规定的级别
（默认 RELEASE_CANDIDATE）。【如只做部分阶段，写明：本次只做 G3–G5】

【无人值守执行规则】
开始调查并执行，直到达到当前目标可验证的交付要求，或遇到无法自行解决的真实外部阻断。
只要执行环境允许，在授权和预算范围内仍有有价值且可执行的工作，就继续研究、开发、测试、
检查、返工和扩展。普通技术决策自行处理，不需要我进行阶段审批。完成一个小功能、一个里程碑
或一个版本，不构成自动停止条件。发现质量不达标，必须自主定位问题并返工。一个任务受阻，
应继续其他不依赖该任务的工作。不允许通过空循环、重复无意义操作或虚假汇报制造工作时长。
会话或执行环境终止时保存真实检查点，不声称仍在后台执行。
无人值守意味着自主完成已授权目标，不意味着无限扩大目标。

每个实质里程碑都更新 GAME.json、GATES、BACKLOG 和 HANDOFF，并创建只包含本任务改动的本地提交。
未经明确授权，不 push、不公开部署、不付费、不删除无关文件。现在开始实际工作。
```
