# Game Reverse Engineering Skill

**研究一款参考游戏，交付经过能力等价验证、可以反复用来做新游戏的 2D Creator Ready Base。** 与 Agent 无关，支持无人值守、跨会话和跨设备接续，兼容 [game-production v4](../../README.md) 的工作区与 Base 版本。

- 规则：[`SKILL.md`](SKILL.md)
- 启动提示词：[从链接开始](prompts/START.md) · [接管已有工程或 v4 Base](prompts/TAKEOVER.md) · [接续](prompts/RESUME.md)
- 验收核心：[能力等价矩阵](references/CAPABILITY_PARITY.md) 与 [Base 验收规则](references/BASE_ACCEPTANCE.md)（Logic Ready → Presentation Ready → Creator Ready，权利另设门禁）
- 规范：[逆向研究](references/RESEARCH.md) · [复用评估](references/REUSE_ASSESSMENT.md) · [动态行为](references/DYNAMIC_BEHAVIOR.md) · [逻辑重建](references/LOGIC_REBUILD.md) · [2D 表现](references/PRESENTATION_2D.md) · [资源与动画管线](references/ASSET_ANIMATION_PIPELINE.md) · [无人值守与恢复](references/AUTONOMY_RECOVERY.md) · [项目经验](references/LESSONS.md) · [与 v4 的关系](references/V4_INTEGRATION.md)

## 安装
Agent 会按启动提示词自动完成。手动安装：

```bash
git clone --depth 1 https://github.com/Chalmo8888/game-production.git /tmp/gp
python /tmp/gp/skills/game-reverse-engineering/scripts/gre.py init --project "<工作区>" \
  --code-path engine --core-path engine/core --reference "<参考游戏链接>"
python "<工作区>/.agents/skills/game-reverse-engineering/scripts/gre.py" resume --project "<工作区>"
```

`init` 只安装本目录 `SHA256SUMS.txt` 中列出的文件，不覆盖已有文件；在 v4 工作区中只新增 `.production/bases/<id>/re/` 记录。需要 Python 3.9+（仅标准库）。

## 测试
```bash
python -m unittest discover -s skills/game-reverse-engineering/tests -v
```
