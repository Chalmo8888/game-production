# 研究原游戏并建立可复用 Base（循环 A）

适用场景：你有一个原游戏链接、开源项目或已有源码，希望先研究成熟机制，建立以后可以反复用来做新游戏的 Base。本次**不**自动制作游戏；需要连同第一款游戏一起完成时，请使用 [START_FULL_PIPELINE](START_FULL_PIPELINE.md)。

> 需要完整的 2D 逆向（包括动画、渲染、特效、资源管线和音频），并交付经过能力等价矩阵和两套原创测试配置验证的 Creator Ready Base 时，推荐使用独立 Skill [game-reverse-engineering](../skills/game-reverse-engineering/prompts/START.md)。本页提示词仍然有效。

替换【】中的内容后整段发送：

```text
请按照 Game Production Skill，研究下面的参考游戏，并建立一个可复用的游戏 Base。

参考游戏/项目（链接、开源仓库或本地工程路径）：
【粘贴链接或描述】

Game Production Skill：
https://github.com/Chalmo8888/game-production

Base 的目标与范围：
【例如：提取塔防核心机制，建立可以通过配置新增单位/关卡/资产的 H5 Base，后续用来做多款不同题材的游戏】

请先阅读 Skill 仓库的 README.md、SKILL.md 和 prompts/START_RESEARCH.md。若当前项目已有
.agents/skills/game-production/，以项目内的固定版本为准。确认当前目录和已有工程后，用
scripts/project.py init --target base --reference <参考链接> 初始化工作区（不覆盖已有文件；
v3 项目改用 migrate）。用户原话写入授权范围的 basis。

本次授权范围是 base：完成 R0 → R1 → R2，达到 BASE_READY 即可交付并停止。
未经我明确要求，不要创建游戏子项目。

R0：确认最终目标、目标平台、授权边界、已有工程和可用工具。
R1：按需研究源码结构、机制与状态机、数值与配置、单位/敌人行为、关卡结构、动画与资源管线、
原版运行行为、技术依赖和商业授权边界。机制矩阵中保留 VERIFIED / STATIC_ONLY / INFERRED /
PROXY / UNKNOWN 的区分。没有使用权利的反编译代码，不能改写后当作可商用代码；隔离研究，
只提炼通用机制。
R2：有合法依据的现成实现优先复用和适配，不默认重写引擎。建立核心玩法、数据配置接口、
资源与动画接口、关卡/内容扩展接口、构建与测试、示例内容和版本记录。用 base register 登记，
B01–B08 逐项取得证据，并区分 RESEARCH_READY / BASE_READY / COMMERCIAL_BASE_CANDIDATE。
达到 BASE_READY 后冻结基线（base update --freeze），在 CAPABILITIES.md 中写清扩展点、
资产接口和已知限制。BASE_READY 不意味着原版已全部逆向，也不意味着某款游戏已经完成。

【无人值守执行规则】
开始调查并执行，直到达到当前目标可验证的交付要求，或遇到无法自行解决的真实外部阻断。
只要执行环境允许，在授权和预算范围内仍有有价值且可执行的工作，就继续研究、开发、测试、
检查、返工和扩展。普通技术决策自行处理，不需要我进行阶段审批。完成一个小功能、一个里程碑
或一个版本，不构成自动停止条件。发现质量不达标，必须自主定位问题并返工。一个任务受阻，
应继续其他不依赖该任务的工作。不允许通过空循环、重复无意义操作或虚假汇报制造工作时长。
会话或执行环境终止时保存真实检查点，不声称仍在后台执行。
无人值守意味着自主完成已授权目标，不意味着无限扩大目标。

记录状态到 .production/，在稳定检查点创建本地 Git commit。未经明确授权，不 push、不公开部署、
不购买付费服务、不上传未授权素材、不删除无关文件、不修改无关项目或生产环境。

最终报告：Base 位置与版本、就绪度及证据、核心能力与扩展点、来源审查结论、未通过事项，
以及下一步如何用 START_NEW_GAME 基于它制作第一款游戏。现在开始实际工作，不要只回复计划。
```
