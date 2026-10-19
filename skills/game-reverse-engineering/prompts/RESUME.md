# 跨会话、跨设备、换 Agent 接续

适用场景：会话中断、上下文被压缩、换了另一个 Agent 软件，或者换了一台电脑。

```text
请使用当前项目中的 Game Reverse Engineering Skill，接续之前的逆向与 Base 建设工作。

1. 读取 .agents/skills/game-reverse-engineering/SKILL.md（不能自动发现时显式读取；项目中没有时，从
   https://github.com/Chalmo8888/game-production 的 skills/game-reverse-engineering 目录获取）。
2. 运行 python .agents/skills/game-reverse-engineering/scripts/gre.py resume --project .
   以文件为准，不依赖旧聊天：检查点、未关闭任务、STALLED 警告、等级与缺口、分工、Git 状态。
3. 确认上一位写入者已经交接，不覆盖本地改动。换设备时运行 gre.py env，重新安装依赖，
   研究原件（research-private/）缺失时按 BASE_HANDOFF 的说明补齐或继续不依赖它们的工作。
4. 用 gre.py assign --agent <你的标签> --scope <本次范围> 记录分工；处理遗留的 ACTIVE 任务：确认进程状态后，
   用 gre.py task recover --id <任务> --recover-action restart|abandon --summary "..." 安全关闭或重启，
   只结束该任务记录的进程。提示缺少新版本字段时运行 gre.py upgrade（只增加字段）。
5. 先跑 Base 的构建和测试；status 中列为“过期”的条目说明代码改过，要重新验证。然后从检查点的
   下一步或 gre.py next 排名第一的缺口继续。

【无人值守执行规则】
开始调查并执行，直到达到当前授权范围内可验证的交付目标，或遇到无法自行解决的真实外部阻断。
只要执行环境允许、授权与预算范围内仍有有价值且可执行的工作，就继续研究、设计、实现、测试、
检查、返工和扩展。不要因为完成一个小版本、研究文档或演示程序就主动停止。优先解决对 Base 能力
和可复用性影响最大的缺口。如果工具挂起，及时检测并恢复。如果某项工作受阻，记录原因并继续其他
可执行任务。同一方案连续失败，应重新调查根因，不无意义重试。测试结果必须保留历史证据，不得直接
覆盖重要记录。不要通过空转、重复小修和无效提交制造工作时长。执行环境中断时，保存精确状态与
恢复入口，不假装仍在后台运行。

交接或暂停前：填写 re/BASE_HANDOFF.md，运行 gre.py checkpoint --next "<下一步>" 和
gre.py handoff --project .（结果为 COMPLETE）。未经明确授权，不 push、不付费、不公开部署。
现在开始实际工作。
```
