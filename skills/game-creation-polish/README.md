# Game Creation & Polish（预览版 0.1.0-preview）

在 [game-reverse-engineering](../game-reverse-engineering/README.md) 交付的 Creator Base 上制作和打磨具体游戏。每个游戏在 `games/<id>/` 中独立完成策划、美术与资源、内容开发、实机 QA 返工和发行候选准备。

**状态：PREVIEW（未完成）。** 已实现并有自动测试的：游戏记录与阶段、D/Q/R 门禁与就绪度推导、Base 创作交接校验（字段、文件哈希、核心指纹、等级、权利）、授权范围与停止状态、跨设备环境探测、交接检查。没有实现：自动美术生产、浏览器实机 QA、打包；也没有在真实游戏上完成过端到端验证。详见 [SKILL.md](SKILL.md) 第 7 节。

## 使用
1. Base 工作区中已有 `gre.py export` 导出的 `CREATOR_HANDOFF.json`。
2. `python skills/game-creation-polish/scripts/gcp.py init --project <工作区根目录>`（按 SHA256SUMS 安装到 `.agents/skills/game-creation-polish/`，不创建也不修改 Base 记录）。
3. 把 [prompts/START.md](prompts/START.md) 的提示词发给 Agent；接续时用 [prompts/CONTINUE.md](prompts/CONTINUE.md)。

## 测试
```text
python -m unittest discover -s skills/game-creation-polish/tests -v
```
需要 Python 3.9+，只用标准库。测试会在临时目录中构造工作区和交接文件，不访问网络，也不读取真实游戏工程。
