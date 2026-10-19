# 安装兼容性与官方资料

核对日期：2026-10-19。这里只核对 Skill 文件结构、发现位置和 Git 工作树；不声称在用户每个版本的客户端实际测试过自动发现。

1. Agent Skills specification：https://agentskills.io/specification
   `SKILL.md` + YAML 元数据；支持 scripts/references/assets；详细资料按需加载。
2. Cursor Skills：https://cursor.com/docs/skills
   官方列出项目 `.agents/skills/` 与 `.cursor/skills/`；使用项目内统一位置避免工具分叉。
3. OpenAI Codex Skills：https://developers.openai.com/codex/skills
   当前会跳转至 https://learn.chatgpt.com/docs/build-skills ，记录仓库 `.agents/skills/` 发现规则。
4. Git worktree：https://git-scm.com/docs/git-worktree
   并行工作可使用不同工作树/分支；不是跨设备自动同步和分布式锁。

优先将整个 `game-production` 文件夹放进游戏的 `.agents/skills/`。不能自动发现的 Agent 使用显式“读取完整路径的 SKILL.md 并执行”，不需要特定斜杠命令。用户安装版本能力不同，应实测；发现失败不等于可以跳过 Skill 规则。

本包的项目状态格式（Workspace / Base / Game 三层）和调度、质量、来源策略是本项目维护的通用工作流设计，不是上面工具厂商的内置保证。生成工具、浏览器和计费能力需每台设备实测。

v4 的 `project.py init` 只安装 `SHA256SUMS.txt` 清单中列出的发布文件，不会把 `.git/`、缓存或本地临时文件拷进游戏项目；已安装副本可以用同一份清单核对完整性。
