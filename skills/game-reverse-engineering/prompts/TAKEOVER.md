# 接管已有工程或已有 v4 Base

适用场景：已经有一个做到一半的研究或引擎工程、一个 game-production v4 工作区，或者旧的 v3 项目，希望用本 Skill 把它升级成 Creator Ready Base。

```text
请使用 Game Reverse Engineering Skill，接管当前目录中已有的研究或引擎工程，把它升级成可复用的 2D Base。
不要从零重做，不要修改任何已有的游戏工程。

Skill 仓库：https://github.com/Chalmo8888/game-production（使用 skills/game-reverse-engineering 目录；
项目中已有 .agents/skills/game-reverse-engineering/ 时以项目内版本为准）
交付目标：【例如：Creator Ready；只要求 Logic Ready 时写 LOGIC_READY】
参考游戏或原始资料：【链接，或说明已在 research-private/ 中】

1. 检查 Git 状态、已有文档、源码规模、测试、构建命令和研究资料，不覆盖未提交的改动。
2. 判断记录格式：
   - 有 .production/WORKSPACE.json（v4）：gre.py init --project . --base-id <已有 Base> --core-path <引擎核心>，
     只新增 re/ 记录，v4 的工作区、Base 和游戏记录保持不变。
   - 只有 v3 记录（.production/PROJECT.json）：先用 game-production 的 scripts/project.py migrate 升级。
   - 没有任何记录：gre.py init --project . --code-path <现有引擎目录> --core-path <核心目录>，不移动代码。
3. 把已有成果映射进能力等价矩阵：已有的测试、录屏、测量和研究文档作为证据加入（先用 gre.py evidence 存档），
   旧报告中“已完成”的结论只有在证据仍然有效时才保留。只有接口或文档的能力记为 INTERFACE_ONLY/DOCUMENTED。
4. 完成 REUSE.json 与 RE01，再按 status 列出的最大缺口推进：研究过多而 Base 不足时先补 Base；
   只有逻辑没有表现时补 P1–P8；然后做两套原创测试配置的 Creator 验证。

【无人值守执行规则】
开始调查并执行，直到达到当前授权范围内可验证的交付目标，或遇到无法自行解决的真实外部阻断。
只要执行环境允许、授权与预算范围内仍有有价值且可执行的工作，就继续研究、设计、实现、测试、
检查、返工和扩展。不要因为完成一个小版本、研究文档或演示程序就主动停止。优先解决对 Base 能力
和可复用性影响最大的缺口。如果工具挂起，及时检测并恢复。如果某项工作受阻，记录原因并继续其他
可执行任务。同一方案连续失败，应重新调查根因，不无意义重试。测试结果必须保留历史证据，不得直接
覆盖重要记录。不要通过空转、重复小修和无效提交制造工作时长。执行环境中断时，保存精确状态与
恢复入口，不假装仍在后台运行。

在稳定检查点创建只包含本任务改动的本地提交。未经明确授权，不 push、不公开部署、不付费、
不上传研究原件、不删除无关文件。现在开始实际工作。
```
