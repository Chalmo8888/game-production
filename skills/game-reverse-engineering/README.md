# Game Reverse Engineering Skill（2.0.0）

**用户只需提供网页游戏链接，Agent 就尽可能自动研究并还原该游戏成熟的玩法与制作能力，最终生成一个能够快速替换美术、修改玩法、批量生产原创游戏的 Creator Base。** 这是目标，不是保证：原版无法运行、没有合法原版素材、无法组织独立验收等真实阻断会被如实记录，等级停在证据支持的位置。与 Agent 无关，支持无人值守、跨会话和跨设备接续。

- 规则：[`SKILL.md`](SKILL.md)
- 启动提示词：[从链接开始](prompts/START.md) · [接管已有工程或 Base](prompts/TAKEOVER.md) · [接续](prompts/RESUME.md)
- 交付等级：LOGIC_READY → PRESENTATION_READY → CREATOR_CANDIDATE → CREATOR_READY（[Base 验收](references/BASE_ACCEPTANCE.md)），权利另行记录。
- 2.0.0 新增：原版管线优先（参考资料盘点、PR01–PR13 的 A/B/C/D 判定、帧研究、结论更正、机制与视觉保真度分开）、PX09 几何契约实验、解耦门禁、创作者工具包、干净首次使用门禁、独立 Agent 复用验收、`stop`、`base bump|freeze`、`export` 创作交接。旧记录可以读取，`gre.py upgrade` 只增加字段。
- 规范：[逆向研究](references/RESEARCH.md) · [复用评估](references/REUSE_ASSESSMENT.md) · [动态行为](references/DYNAMIC_BEHAVIOR.md) · [逻辑重建](references/LOGIC_REBUILD.md) · [2D 表现](references/PRESENTATION_2D.md) · [资源与动画管线](references/ASSET_ANIMATION_PIPELINE.md) · [能力等价矩阵](references/CAPABILITY_PARITY.md) · [无人值守与恢复](references/AUTONOMY_RECOVERY.md) · [项目经验](references/LESSONS.md) · [创作交接](references/CREATION_HANDOFF.md)
- 下游：具体游戏由 [game-creation-polish](../game-creation-polish/README.md)（预览版）读取 `CREATOR_HANDOFF.json` 后制作。

## 安装
Agent 会按启动提示词自动完成。手动安装：

```bash
git clone --depth 1 https://github.com/Chalmo8888/game-production.git <临时目录>/gp
python <临时目录>/gp/skills/game-reverse-engineering/scripts/gre.py init --project "<工作区>" \
  --code-path engine --core-path engine/core --starter-path content/starter --reference "<参考游戏链接>"
python "<工作区>/.agents/skills/game-reverse-engineering/scripts/gre.py" resume --project "<工作区>"
```

`init` 只安装本目录 `SHA256SUMS.txt` 中列出的文件，不覆盖已有文件；在已有工作区中只新增 `.production/bases/<id>/re/` 记录。需要 Python 3.9+（仅标准库）；干净首次使用门禁另需 Git。Windows、macOS 和 Linux 使用同一套命令，平台差异写在 `FIRST_USE.json` 的 `argv_windows` / `argv_posix` 中。

## 测试
```bash
python -m unittest discover -s skills/game-reverse-engineering/tests -v
```
测试在临时目录中构造工作区和 Git 仓库，不访问网络，也不读取真实游戏工程。
