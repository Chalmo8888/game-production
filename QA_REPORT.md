# 自身测试报告 — game-production 4.1.0 与 game-reverse-engineering 1.0.0

- 审查日期：2026-10-19
- 分支：`feature/game-reverse-engineering`（尚未合并到 main）
- 环境：Windows 10.0.26200，Python 3.12.10。代码只用 Python 3.9 可用的语法和标准库，但没有在 3.9、macOS 或 Linux 上实际运行过。
- 独立性：self_review（同一个 Agent 编写并测试），没有独立审查者。

## game-reverse-engineering 1.0.0
`python -m unittest discover -s skills/game-reverse-engineering/tests -v`：**21/21 通过**，没有跳过的测试。

| 验收场景 | 测试 | 验证内容 |
|---|---|---|
| 空项目启动 | `test_empty_folder_start_…` | 创建 v4 兼容工作区（范围：只做 Base，game_quota = 0）、Base 和 re/ 记录；按清单精确安装；等级为 NONE；v4 `validate` 通过 |
| 已有项目接管 | `test_existing_project_takeover_…` | 源码哈希不变；intake 记为 adopt_existing；保留已有 AGENTS 规则；重复初始化不重复追加 |
| 代码可以合法复用 | `test_legally_reusable_code_path` | 没有许可证据时拒绝 KEEP；有证据后，条目可以按 REUSE 方式 VERIFIED |
| 代码不能合法复用 | `test_code_that_cannot_be_legally_reused` | 没有授权的反编译代码不能 KEEP；隔离路径与核心重叠时拒绝；隔离模块不能作为实现来源，只能作为研究依据 |
| 无法动态运行原作 | `test_static_only_evidence_…` | STATIC_ONLY 必须写 dynamic_gap；原版 VERIFIED 需要动态证据；UNKNOWN 不得进入实现（IMPROVE 例外）；本地研究原件缺失只给警告；状态中列出静态条目 |
| 逻辑完成但表现未完成 | `test_logic_ready_does_not_pass_presentation`、`test_presentation_domain_cannot_be_skipped_entirely` | LOGIC_READY 可以声明，PRESENTATION_READY 被拒；INTERFACE_ONLY 不计入；只有单元测试的表现条目被拒；表现域不能整体 N/A；手动改写的声明被发现 |
| 两套测试资源的 Creator 验证 | `test_creator_ready_needs_two_distinct_probes_…` | 只有一套时被拒；复制出来的第二套被判定为“相同”；两套原创配置通过 `--strict-target`；修改核心后，原来的 Creator 声明被发现失效 |
| 中断后恢复 | `test_interrupted_session_resumes_from_files` | 研究任务必须指向矩阵条目；超时任务提示 STALLED；新会话的 resume 显示检查点；连续失败提示 REPEATED_FAILURE |
| 不同 Agent 接续 | `test_handoff_between_different_agents` | 空交接模板和 ACTIVE 任务都会让交接检查失败；补齐后 COMPLETE；Agent B 接手后，状态和历史中都有记录 |
| v4 旧项目迁移 | `test_v4_project_migration_keeps_v4_records` | 用 v4 工具建立的工作区、Base 和游戏在接管后字节不变（AGENTS/.gitignore 只追加）；v4 与 GRE 的 validate 都通过 |

其他测试：
- v3 项目被拒，并提示先迁移。
- 自带的 v4 模板与根目录模板一致。
- 证据另存不覆盖；被改动或删除的历史证据会被发现；删除条目历史会被发现。
- 研究空转和打磨空转的防护。
- 权利与技术等级分开（RE02 自审被拒，外部批准通过且不影响等级）。
- Base 升版本后必须重新验证；报告按时间戳另存。
- CRLF 检出的副本仍能正确安装；CLI 退出码。

**变异检查**：分别关闭以下四项规则后，对应测试都会失败，说明测试确实能发现问题：
- 表现条目必须有运行时或测量证据；
- 测试配置的核心指纹一致；
- 隔离模块不得复用；
- 商业许可必须外部批准。

## game-production 4.1.0
`python -m unittest discover -s tests -v`：**32/32 通过**（与 4.0.0 相同的测试集；根目录清单不再包含 `skills/` 后，“按清单精确安装”测试继续通过）。

## 其他检查
- README 中的四段启动提示词（逆向 START、研究、新建游戏、一次性完整生产）与对应的提示词文件逐字一致。
- 仓库内所有相对 Markdown 链接都指向存在的文件。
- 两份 SHA256SUMS（根目录、`skills/game-reverse-engineering/`）与实际文件一致。
- 扫描私钥、令牌和密码赋值：无命中。经验文档只引用各项目内的相对路径，不包含本机绝对路径或任何原作代码与素材。

## 不在本报告范围内
工具不运行原作，不调用反编译器，不生成美术，不做法律判断。本报告不代表任何一款 Base 或游戏已经达到相应等级，也不代表 Agent 客户端一定会自动发现 Skill。
