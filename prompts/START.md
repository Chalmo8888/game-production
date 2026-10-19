# 启动入口选择（v3 链接兼容页）

v4 把原来的单一 START 拆成了几个场景入口。v3 的提示词如果引用了本文件，请按下表选择对应的入口，并整段复制其中的提示词。所有规则以 [SKILL.md](../SKILL.md) 为准，本页不重复列出规则。

| 你的情况 | 使用 |
|---|---|
| 有参考游戏，先研究并建立可复用 Base | [START_RESEARCH.md](START_RESEARCH.md) |
| 一次性完成研究、Base 和第一款游戏 | [START_FULL_PIPELINE.md](START_FULL_PIPELINE.md) |
| 已有 Base，制作一款新游戏 | [START_NEW_GAME.md](START_NEW_GAME.md) |
| 按约定的清单连续制作多款游戏 | [BATCH_PRODUCTION.md](BATCH_PRODUCTION.md) |
| 继续某款未完成的游戏 | [CONTINUE_GAME.md](CONTINUE_GAME.md) |
| 接管已经开发到一半的工程（含 v3 项目） | [ADOPT_EXISTING.md](ADOPT_EXISTING.md) |
| 换设备、换软件、开新会话 | [RESUME.md](RESUME.md) |
| 只做美术和音频 | [ART_PRODUCTION.md](ART_PRODUCTION.md) |
| 只做指定的阶段 | [STAGE.md](STAGE.md) |
| 审查、找问题 | [REVIEW_GAME.md](REVIEW_GAME.md) |
| 暂停并交给其他 Agent | [HANDOFF.md](HANDOFF.md) |

如果 Agent 是按 v3 提示词来到这里的：先读取 README.md 和 SKILL.md，判断当前目录属于上表哪种情况，再按对应入口执行。当前目录已有 v3 记录（`.production/PROJECT.json`）时，按 [ADOPT_EXISTING.md](ADOPT_EXISTING.md) 运行 `migrate`。不要因此停下等待确认。
