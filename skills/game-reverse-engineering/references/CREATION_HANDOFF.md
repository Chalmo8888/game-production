# 创作交接：交给 game-creation-polish

本 Skill 负责把参考游戏研究透并建成 Base；具体游戏的策划、美术、开发、QA 和发行准备由 [game-creation-polish](../../game-creation-polish/SKILL.md) 负责。两者之间只有一个接口：`gre.py export` 写出的 `CREATOR_HANDOFF.json`。

## 共用的工作区格式
- `.production/WORKSPACE.json`（schema 3.0）：Base 与游戏登记表、焦点、授权范围、权限。本 Skill 初始化时默认授权范围为 Base（`game_quota = 0`），不会自动创建游戏。
- `.production/bases/<id>/BASE.json`：版本列表与 `current_version`。交付等级不写在这里，而由 `re/` 下的记录推导。
- `.production/bases/<id>/re/`：本 Skill 的全部研究与验收记录。
- `.production/bases/<id>/handoff/<version>/`：每次 `export` 新建一份交接文件，从不覆盖。
- `games/<id>/`：由 game-creation-polish 创建和维护，本 Skill 不写。

已有的同格式工作区（包括以前的单 Skill 版本创建的）可以直接 `init --base-id <id>` 接管，已有记录不变。v3 单游戏记录不受支持。

## 交接文件包含什么
等级（由证据推导）、Base 版本、Git 提交、核心路径与指纹、starter 路径、机制与视觉两类保真度、RE01/RE02/RE03 权利状态与残余风险说明、首次使用结果、独立复用状态、到下一等级还缺什么，以及工具包和 BASE_HANDOFF 文件的哈希。字段说明见 game-creation-polish 的 [交接契约](../../game-creation-polish/references/HANDOFF_CONTRACT.md)。

## 下游怎样使用
- game-creation-polish 会核对 schema、Base ID/版本、每个文件的哈希和重新计算的核心指纹；任一不符就视为没有交接。
- 游戏只有在交接完整且等级 ≥ CREATOR_CANDIDATE 时才能达到 GAME_READY；公开发布批准还要求 RE01 PASS、RE03 PASS 或 N/A。
- CREATOR_CANDIDATE 的 Base 可以开始做游戏，但交接会写明独立复用尚未通过，下游必须如实转述。

## Base 变化的流程
1. 游戏侧发现 Base 缺陷或需要新的通用能力，记录在游戏的 `core_extensions.proposed_for_base`，交回本 Skill。
2. 本 Skill 在分支或独立工作树中修改，`gre.py base bump --version <新版本> --summary "<改了什么，是否破坏兼容>"`。
3. 新版本重新取得等级（相关条目、PX 检查、首次使用和独立复用都会因核心指纹变化而过期）。
4. `gre.py export` 导出新版本的交接；游戏侧 `gcp.py game rebind` 后回归。
5. 已冻结的旧版本（`gre.py base freeze`）保留，旧游戏可以继续绑定。
