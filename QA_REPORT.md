# Game Production Skill v4.0.0 — 自身测试报告

- 审查日期：2026-10-19
- 环境：Windows 10.0.26200，Python 3.12.10。代码只用 Python 3.9 可用的语法和标准库，但未在 3.9、macOS 或 Linux 上实际运行过。
- 范围：Skill 结构、辅助工具 `scripts/project.py`（工作区/Base/游戏记录、就绪度判定、隔离、迁移）、提示词与文档链接、打包完整性。
- 独立性：self_review（同一个 Agent 编写并测试），没有独立审查者。

## 自动测试
`python -m unittest discover -s tests -v`：**32/32 通过**。

| 验收场景 | 测试 | 验证内容 |
|---|---|---|
| A 空文件夹 + 原游戏链接 | `test_a_…` | 创建研究登记和 Base 记录（NONE）；没有证据时拒绝 BASE_READY；B01 PASS 后可以声明 RESEARCH_READY |
| B 已有 Base 创建 Game 01 | `test_b_…` | 独立的 design/ 与 .production/，绑定 core@1.0.0，阶段 G1 待开始，不复制引擎，Base 记录依赖 |
| C 同一 Base 创建 Game 02 | `test_c_…` | Game 01 的文件哈希前后一致；`..` 引用 Game 01 的证据被拒；JSON 引用其他游戏目录报错；目录嵌套被拒 |
| D 美术阶段交给另一个 Agent | `test_d_…` | next_action 为空或 HANDOFF 是空模板时交接检查失败；补齐后新会话的 status 恢复 G4、assignment 和下一步 |
| E 换设备 | `test_e_…` | 在复制出来的工作区上重新探测，共享记录哈希不变，只更新本地 ENVIRONMENT；共享记录写入设备路径时报错 |
| F Base 升级 | `test_f_…` | bump 后列出需要回归的游戏；旧版本证据不能声明新版本就绪；改绑后就绪度自动降低，补齐新版本证据后恢复 |
| G 视觉 QA 未通过 | `test_g_…` | Q04 FAIL 时拒绝 RELEASE_CANDIDATE 和 G6 DONE；手动改写声明会被 validate 发现 |
| H 缺少授权或来源记录 | `test_h_…` | Base 缺少 B02（商用代码来源）、Q08 为 N/A、R04 是 self_review，三种情况都拒绝 PUBLICATION_APPROVED，也拒绝 PUBLISHED |
| I v3 工作区迁移 | `test_i_…`（2 项） | v3 记录字节不变，任务、下一步、权限和阶段保留，旧 PASS 证据继续按哈希校验；旧 Skill 被存档；AGENTS 中只替换 v3 块；有本地改动的旧 Skill 需要 `--accept-archive` |
| J 单 Agent 连续推进 | `test_j_…` | G1 DONE 后焦点自动移到 G2、状态为 RUNNING；目标未满足时拒绝 TARGET_REACHED；证据齐全后允许 |

其他测试：按清单精确安装（不含 `.git`）、CRLF 检出的 Skill 副本仍能以 LF 正确安装、重复初始化不覆盖、保留已有 AGENTS 与游戏代码、拒绝旧版 totop、拒绝覆盖已修改的 Skill、batch 必须指定数量、超出授权范围需要用户请求、批量三款到达配额后停止、stage/review 模式限制写入（目标不变时切换模式保留游戏列表）、策划模板未填写或缺节时拒绝 D01、已生成的图片不能算已集成、证据篡改与缺失、PASS 缺少 base_version、删除门禁与 N/A 无依据、停止状态必须写原因、路径穿越与符号链接逃逸、损坏的 JSON、CLI 退出码。

## 其他检查
- README 中三段启动提示词与 `prompts/START_RESEARCH.md`、`START_NEW_GAME.md`、`START_FULL_PIPELINE.md` 逐字一致。
- 仓库内 75 个相对 Markdown 链接全部指向存在的文件。
- 扫描私钥、访问令牌、密码赋值和反编译标记：无命中。唯一的设备路径字符串是测试中故意构造的反例。
- 所有文本文件为 UTF-8、LF、无 BOM；SHA256SUMS 与实际文件内容一致（init 会校验）。

## 不在本报告范围内
工具不启动游戏、不调用 Agent、不进行原游戏逆向、不生成图片或音频、不做法律结论。本报告不代表所有 Agent 客户端都会自动发现 Skill，不保证 Agent 能长时间持续执行，也不代表任何一款游戏达到了发行品质。
