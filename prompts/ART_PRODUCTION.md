# 只负责美术与音频生产（G2 补全 / G4）

适用场景：一个 Agent 或一台设备只负责某款游戏的美术和音频，但必须按资产计划完成导入和运行时验证，而不只是出图。执行者不限软件。

```text
请按照当前项目中的 Game Production Skill，只负责游戏【game-id】的美术与音频生产。

请读取 .agents/skills/game-production/SKILL.md 和 references/ART_DIRECTION_GUIDE.md、
references/ASSET_PIPELINE.md，以及 games/<id>/design/ 下的 ART_DIRECTION.md、ART_ASSET_PLAN.md、
ANIMATION_SPEC.md、GAME_DESIGN.md，games/<id>/.production/ASSETS.json、GAME.json、HANDOFF.md，
还有绑定 Base 的 CAPABILITIES.md（资产接口）。

本次是 stage 模式，允许的阶段为【G4；如果美术策划尚未完成，写 G2,G4】。用
project.py scope --target <沿用当前目标> --mode stage --allowed-stages <阶段> --basis "<我的原话>"
记录本次范围（目标不变时会保留已有的游戏列表），再用
project.py game update --id <id> --assign-agent <你的标签> --assign-stages <阶段> 记录分工，
不要修改游戏的最终目标。

要求：
- 按 ART_ASSET_PLAN 的优先级和批次生产；G2 尚未完成时，先完成美术策划，并用一个代表资产
  走完“需求 → 生成/制作 → 加工 → 导入 → 动作播放 → 实机检查 → 逻辑回归”。
- 只使用本机真实可用、在预算授权内的工具（生图、建模、动画、脚本加工、音频生成、合法素材），
  记录实际调用。工具不可用时，把对应资产标为受阻，继续做其他可推进的资产或加工工具，
  不伪造生成结果。
- 在 ASSETS.json 中如实推进状态：source_generated → processed → integrated → verified。
  “图片已生成”不等于美术完成；integrated/verified 必须有运行时文件的哈希和许可依据，
  verified 必须有实机证据。
- 风格、比例、锚点、朝向和动作必须符合规格；不得要求引擎不支持的格式。
  仅美术改动不应改变伤害、移动或冷却，需要做逻辑回归。
- 所有素材写入 RIGHTS_LEDGER（来源、工具条款、许可）。不使用商业游戏的素材。
- 不修改游戏逻辑和 Base；发现依赖缺陷时，记录任务交给实现阶段，只做本阶段必要的局部兼容修复。

【无人值守执行规则】
开始调查并执行，直到达到当前目标可验证的交付要求，或遇到无法自行解决的真实外部阻断。
只要执行环境允许，在授权和预算范围内仍有有价值且可执行的工作，就继续研究、开发、测试、
检查、返工和扩展。普通技术决策自行处理，不需要我进行阶段审批。完成一个小功能、一个里程碑
或一个版本，不构成自动停止条件。发现质量不达标，必须自主定位问题并返工。一个任务受阻，
应继续其他不依赖该任务的工作。不允许通过空循环、重复无意义操作或虚假汇报制造工作时长。
会话或执行环境终止时保存真实检查点，不声称仍在后台执行。
无人值守意味着自主完成已授权目标，不意味着无限扩大目标。

阶段完成后：更新游戏 HANDOFF 和 next_action，运行 project.py handoff --game <id> --check，
将运行状态设为 HANDOFF_READY。阶段完成不代表游戏完成。未经明确授权，不 push、不付费、
不上传未授权素材。现在开始实际工作。
```
