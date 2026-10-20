# 在已交付的 Creator Base 上开始一款新游戏

适用场景：工作区里已经有 game-reverse-engineering 交付的 Base（并已 `gre.py export` 导出创作交接），你只需要说出新游戏的主题和目标。本 Skill 为预览版，流程中的美术生产、实机 QA 和打包仍由 Agent 按规则执行，工具只记录和校验。

替换【】中的内容后整段发送（在 Base 工作区中打开 Agent）：

```text
请使用 Game Creation & Polish Skill，基于现有 Creator Base 制作一款新游戏。

新游戏主题与目标：
【例如：主题为深海探索，单位和关卡与示例内容明显不同，完成可游玩的本地发行候选包】

使用的 Base：【留空表示当前焦点 Base 的当前版本；或写 core@1.2.0】

Skill：项目中的 .agents/skills/game-creation-polish/SKILL.md；没有时先读取
https://github.com/Chalmo8888/game-production 的 skills/game-creation-polish/SKILL.md，
并运行其中的 gcp.py init --project <工作区根目录> 安装。

1. 运行 gcp.py status，确认 Base 的创作交接等级（需要 CREATOR_CANDIDATE 或 CREATOR_READY）、
   机制/视觉保真度、独立复用状态和未完成项。交接缺失或被改动时，先告诉我需要回到
   game-reverse-engineering 处理，可以同时开始策划，但不得把游戏标为 GAME_READY。
2. 读 Base 的 START_HERE、BASE_HANDOFF 和创作者工具包（场景几何、角色规范、图层、动画导入、
   UI 主题、内容包工具、资产校验器）。
3. gcp.py game create --id <新 slug> --base <base@version> --user-request "<我的原话>"，
   在 games/<slug>/ 下建立独立记录，不复制引擎。
4. G1 策划（GAME_DESIGN 17 节）→ G2 美术策划并用一个代表资产走通全链路 → G3 开发 → G4 资产 →
   G5 完整 QA 与返工 → G6 独立打包 → G7 复盘。

只写本游戏的目录，不修改 Base 核心、starter 或工具包；Base 能力不够时记录到
core_extensions.proposed_for_base 并告诉我，不在游戏里改 Base。

【无人值守执行规则】
开始执行，直到达到当前目标可验证的交付要求，或遇到无法自行解决的真实外部阻断。
只要执行环境允许，在授权和预算范围内仍有有价值且可执行的工作，就继续开发、测试、检查、
返工和扩展。普通技术决策自行处理，不需要我进行阶段审批。完成一个小功能或里程碑不构成
停止条件。质量不达标必须自主定位并返工。一个任务受阻，继续其他不依赖它的工作。
不允许空循环、重复无意义操作或虚假汇报。会话终止时保存真实检查点，不声称仍在后台执行。
完成这款游戏后停止，不要自动开始下一款。

测试通过不等于游戏品质通过；结论绑定版本和证据，未知记为未验证，不得自我放行。
不得使用原版素材或未授权素材作为正式资产。在稳定检查点创建本地 Git commit。
未经明确授权，不 push、不公开部署、不付费、不删除无关文件。

最终报告：游戏目录、绑定的 Base 版本和交接等级、就绪度与证据、运行和打包方式、未通过事项。
现在开始实际工作。
```
