# 接管已有工程或已有 Base

适用场景：已经有一个做到一半的研究或引擎工程，或者一个已有 `.production/WORKSPACE.json` 的工作区（包括以前的单 Skill 版本创建的），希望用本 Skill 把它升级成 Creator Base。

```text
请使用 Game Reverse Engineering Skill，接管当前目录中已有的研究或引擎工程，把它升级成可复用的 2D Creator Base。
不要从零重做，不要修改任何已有的游戏工程。

Skill 仓库：https://github.com/Chalmo8888/game-production（使用 skills/game-reverse-engineering 目录；
项目中已有 .agents/skills/game-reverse-engineering/ 时以项目内版本为准）
交付目标：【例如：CREATOR_READY；只要求逻辑时写 LOGIC_READY】
参考游戏或原始资料：【链接，或说明已在 research-private/ 中】

1. 检查 Git 状态、已有文档、源码规模、测试、构建命令和研究资料，不覆盖未提交的改动。
2. 判断记录格式：
   - 有 .production/WORKSPACE.json：gre.py init --project . --base-id <已有 Base> --core-path <引擎核心> --starter-path <示例内容>，
     只新增 re/ 记录，已有的工作区、Base 和游戏记录保持不变。
   - 只有 v3 单游戏记录（.production/PROJECT.json）：本 Skill 不支持，先告诉我，不要自行改写这些记录。
   - 没有任何记录：gre.py init --project . --code-path <现有引擎目录> --core-path <核心目录>，不移动代码。
   已有的旧记录先运行 gre.py upgrade（只增加字段）。
3. 把已有成果映射进能力等价矩阵：已有的测试、录屏、测量和研究文档先用 gre.py evidence 存档再引用；
   旧报告中“已完成”的结论只有在证据仍然有效时才保留。只有接口或文档的能力记为 INTERFACE_ONLY/DOCUMENTED。
4. 用 gre.py discover 审查原版代码、运行行为和资源结构，补充游戏特有能力；如实标注 PARITY / REPLACEMENT / EXTENSION。
5. 表现系统按原版管线优先重新核对：gre.py present reference 盘点参考资料；PR01–PR13 每项写原版方法、Base 方法和
   A/B/C/D 判定，旧结论有错就用 --correct --affects 更正并重新验证下游；每个场景类型做帧研究；PX01–PX09 实测。
   旧的“已还原”说法如果没有原版证据，改为 C 或 D。
6. 完成 REUSE.json 与 RE01，再按 gre.py next 推进；然后做两套 Creator 测试配置、解耦、创作者工具包、
   干净首次使用（gre.py first-use run），争取独立复用验收，最后 gre.py export。

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
