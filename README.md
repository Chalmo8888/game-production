# ToTop Game Production Skills

本仓库只包含两个 Skill，各有独立入口、版本和 SHA256 清单：

| Skill | 状态 | 负责什么 |
|---|---|---|
| [game-reverse-engineering](skills/game-reverse-engineering/README.md) | 2.0.0 | 用户只需提供网页游戏链接，Agent 尽可能自动研究并还原该游戏成熟的玩法与制作能力，交付能够快速替换美术、修改玩法、批量生产原创游戏的 **Creator Base** |
| [game-creation-polish](skills/game-creation-polish/README.md) | 0.1.0-preview（**未完成**） | 在已交付的 Creator Base 上制作和打磨具体游戏：策划、美术与资源、开发、QA 返工、发行候选 |

两者之间唯一的接口是 Base 导出的 `CREATOR_HANDOFF.json`（[交接契约](skills/game-creation-polish/references/HANDOFF_CONTRACT.md)）。以前的单体 Skill（根目录的 SKILL.md、prompts、references、templates、scripts 和对应测试）已经退役并删除，不再提供入口；其中仍有价值的通用机制已迁入这两个 Skill（见 [CHANGELOG](CHANGELOG.md)）。

## 最快开始：从一个游戏链接得到 Creator Base
打开任何能访问 GitHub、读取文件并执行开发工具的 Agent，把下面的链接换成你的参考游戏后发送：

```text
请使用 https://github.com/Chalmo8888/game-production 中的 skills/game-reverse-engineering，
按其中 prompts/START.md 的规则研究下面的参考游戏，交付 Creator Base：
【粘贴网页游戏链接】
```

完整提示词（含无人值守规则和最终报告要求）：[prompts/START.md](skills/game-reverse-engineering/prompts/START.md)。接管已有工程用 [TAKEOVER](skills/game-reverse-engineering/prompts/TAKEOVER.md)，跨会话或换设备接续用 [RESUME](skills/game-reverse-engineering/prompts/RESUME.md)。

这是目标，不是保证。原版无法运行、没有合法原版素材、无法组织独立 Agent 验收等真实阻断会被如实记录，交付等级停在证据支持的位置：

`LOGIC_READY → PRESENTATION_READY → CREATOR_CANDIDATE → CREATOR_READY`

## 在 Base 上做游戏（预览版）
Base 导出交接后，用 [game-creation-polish 的 START](skills/game-creation-polish/prompts/START.md) 开始一款游戏，用 [CONTINUE](skills/game-creation-polish/prompts/CONTINUE.md) 接续。它目前只实现了游戏记录、阶段与门禁、交接校验和恢复工具；美术生产、实机 QA 和打包没有端到端验证过，详见其 [SKILL.md 第 7 节](skills/game-creation-polish/SKILL.md)。

## 目录
```text
skills/
├── game-reverse-engineering/   SKILL.md · README · prompts/ · references/ · templates/ · scripts/gre.py · tests/ · SHA256SUMS.txt
└── game-creation-polish/       SKILL.md · README · prompts/ · references/ · templates/ · scripts/gcp.py · tests/ · SHA256SUMS.txt
tools/repo_check.py             仓库检查：只有两个 Skill 入口、清单与链接有效、无旧入口残留、无本机路径或密钥
tests/test_repo.py              仓库检查与两个 Skill 之间的交接契约测试
```

## 测试
需要 Python 3.9+（只用标准库）和 Git。Windows、macOS、Linux 命令相同：

```text
python -m unittest discover -s skills/game-reverse-engineering/tests
python -m unittest discover -s skills/game-creation-polish/tests
python -m unittest discover -s tests
python tools/repo_check.py
```

修改 Skill 文件后运行 `python tools/repo_check.py --write-manifests` 重新生成清单（只收录 Git 已跟踪的文件，所以先 `git add`）。

## 边界
- 原版来自可下载游戏、公开仓库或反编译工程，都不代表其代码和美术可以商业使用。研究原件放在被忽略的 `research-private/`，与 Base、示例内容和发行包隔离。
- 权利记录（代码与组件许可、原作素材与表达、用户发布批准）与技术等级分开，都不是法律意见，剩余风险永远不为零。
- 工具只核对记录、哈希、指纹与声明是否一致，不判断玩法、画面品质或法律问题；不能自动判断的事项保持 UNVERIFIED / NOT_RUN，不用形式化测试冒充通过。
- 默认不 push、不公开部署、不付费、不删除无关文件。
