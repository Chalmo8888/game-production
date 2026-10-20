# 无人值守、价值优先级与恢复规则

## 1. 核心指令
> 开始调查并执行，直到达到当前授权范围内可验证的交付目标，或遇到无法自行解决的真实外部阻断。
>
> 只要执行环境允许、授权与预算范围内仍有有价值且可执行的工作，就继续研究、设计、实现、测试、检查、返工和扩展。
>
> 不要因为完成一个小版本、研究文档或演示程序就主动停止。
>
> 优先解决对 Base 能力和可复用性影响最大的缺口。
>
> 如果工具挂起，及时检测并恢复。
>
> 如果某项工作受阻，记录原因并继续其他可执行任务。
>
> 同一方案连续失败，应重新调查根因，不无意义重试。
>
> 测试结果必须保留历史证据，不得直接覆盖重要记录。
>
> 不要通过空转、重复小修和无效提交制造工作时长。
>
> 执行环境中断时，保存精确状态与恢复入口，不假装仍在后台运行。

## 2. 授权范围与停止状态
默认范围是“研究 + Base”。交付目标是 RE_STATE 中的 `target_level`（默认 CREATOR_READY），工作区的 `game_quota = 0`。达到目标就交付并停止：不自动创建游戏，不无限扩展原作细节。

用 `gre.py stop --status <状态> --reason "..."` 记录运行状态：
- `TARGET_REACHED`：工具核对证据推导的等级，未达到 `target_level` 时拒绝，并列出缺口。
- `HANDOFF_READY`：本次分配的阶段已完成，交给下一个 Agent。
- `EXTERNAL_BLOCKED`、`RUNTIME_LIMIT`、`USER_PAUSED`：必须写明真实原因（阻断是什么、试过什么、怎样解除）。
独立复用验收无法组织时，可以在其他工作全部完成后以 EXTERNAL_BLOCKED 停止并说明，等级保持 CREATOR_CANDIDATE。

**预算**：RE_STATE 的 `budget` 记录是否允许付费工具及其上限；未配置时视为零，不认为订阅包含所有 API。

## 3. 价值驱动的任务选择（`gre.py next`）
每轮先运行 `gre.py next`。它为每个未完成的条目打分，并给出建议动作：
| 因素 | 计分 |
|---|---|
| 对核心玩法或表现的影响 | scope：core +4、optional +1、legacy 0；`value.impact` 1–3 |
| 是否阻碍下一等级 | 阻碍下一等级（含 Creator Ready）+4；Creator 测试配置缺失时单列一项，12 分 |
| 对后续新游戏的价值 | 可供新游戏使用、C1 扩展能力、游戏特有能力 +2 |
| 证据是否充分 | 证据足以建设 +2；不足时建议限时研究，预算用完后建议替代方案 |
| 实现成本 | `value.cost` S +2、M +1、L 0 |

建议动作有五种：
- **build**：证据充分，直接建设。
- **verify**：已实现，补运行时或测量证据。
- **re-verify**：代码改动后验证结果过期。
- **time-boxed research**：限时研究，并显示已用的研究次数。
- **stop researching**：研究次数已用完。改用授权明确的成熟组件实现 REPLACEMENT，或者带设计说明独立实现 EXTENSION。

研究与建设形成闭环：每个研究任务都必须指向一个条目（`task start --kind research --item`），研究结论写进条目的 original 字段，然后转入建设。原作细节难以恢复、但有成熟且授权明确的替代技术时（例如开源的物理、补间、粒子或骨骼动画库），先在 REUSE.json 中评估许可和执行边界，再以 REPLACEMENT 方式采用，不必无限研究原作。

## 4. 工具提供的防护
| 防护 | 触发条件 | 处理 |
|---|---|---|
| RESEARCH_BUDGET（拒绝） | 同一条目的研究任务达到 `research_budget_per_item`（默认 3）次仍未实现 | 用现有证据建设，或改为 REPLACEMENT / EXTENSION。只有提出新的具体假设时，才用 `--override-reason` 继续 |
| POLISH_BLOCKED（拒绝） | 存在分数达到 `high_priority_score`（默认 10）的缺口，且连续第 `polish_streak_limit`（默认 5）个任务是 polish/docs | 转去做 `gre.py next` 第一项；确有必要（例如用户指定）时写明 `--override-reason` |
| STALLED | ACTIVE 任务超过 `timeout_min` | 检查记录的进程，然后 `task recover` |
| REPEATED_FAILURE | 同一任务失败或超时达到 `same_failure_limit`（默认 3）次 | 停止重试，查看第一个错误，隔离最小复现，换假设 |
| RESEARCH_SPIN | 最近 6 个任务都是研究，期间没有条目达到 IMPLEMENTED/VERIFIED | 立即为最大缺口建设 |
| POLISH_SPIN | 连续 polish/docs 任务达到上限，而目标未达到 | 回到第一项缺口 |
| NEGLECTED_GAP | 最高分缺口在最近 `neglect_limit`（默认 8）个任务中都没有被处理 | 把它排进下一项任务 |
| 等级声明 | 证据不足时声明更高等级 | `level --set` 拒绝，`validate` 报错 |
| 历史保护 | 证据被改动或删除、条目历史被删、HISTORY 乱序 | `validate` 报错 |

阈值放在 RE_STATE 的 `guards` 中，可以按项目调整，但要写明理由。

## 5. 长任务、工具挂起与安全恢复
- 开始长任务时记录超时和进程信息：`gre.py task start --id T-07 --kind build --timeout-min 30 --pid <pid> --command "<命令>"`。
- 预计耗时很长的命令放到后台，定期查看输出，不要无条件等待。并行的浏览器测试默认最多 2 个；端口冲突时换端口。
- 出现 STALLED 时：
  1. 查看输出是否仍在增长。仍有输出的长构建不要盲目结束。
  2. 确认挂起后，只结束本任务记录的进程（`pid`），不结束无关服务。
  3. 运行 `gre.py task recover --id T-07 --recover-action restart|abandon --summary "<检查了什么，结束了什么>"`。任务被记为 TIMED_OUT（计入失败次数），restart 会以新的超时开始下一次尝试。
  4. 未超时的任务不能 recover，除非加 `--force` 并在 summary 中写明原因。
- 同一任务反复超时，说明方案本身有问题，要换方法（例如分块处理、缩小输入），而不是继续加长超时。

## 6. 证据与代码版本
- 测试、通关、测量、截图等结果用 `gre.py evidence --file <结果>` 按时间戳存入 `re/evidence/`，不覆盖旧文件。报告每次另存。
- 条目验证时记录 Base 版本、相关代码指纹（`code_paths`）和 Git HEAD。相关代码改动后，旧结论自动过期（`status` 中的 Stale verifications），需要重新验证。Creator 测试配置记录整个核心的指纹。
- HISTORY.jsonl 只追加。删除或修改旧证据、删除条目历史都会被 `validate` 发现。

## 7. Git 基线、检查点与恢复
- 开始前记录 `git status` 与 HEAD，不覆盖别人的未提交改动；只提交本任务的改动，不 force push。
- 核心与 starter 路径有未提交改动时，工具不承认 CREATOR_CANDIDATE 及以上等级：首次使用门禁测试的是已提交的 HEAD，交付的必须就是被测试的。
- 等级声明记录当时的 Git HEAD 和核心指纹，便于事后复核。
- 在完成实质任务后、做风险改动前、会话余量不足时和交接前，运行 `gre.py checkpoint --next "<下一项具体任务和命令>"`，并创建只包含本任务改动的本地 Git 提交。
- 中断后（同一 Agent 的新会话、另一个 Agent 或另一台设备）：
  1. 运行 `gre.py resume`。
  2. 处理遗留的 ACTIVE 或 STALLED 任务。
  3. 换设备时运行 `gre.py env`，并跑 Base 的构建和测试。
  4. 从检查点或 `gre.py next` 继续。
- 不声称会话结束后仍在后台工作。没有可执行任务时，如实记录阻断及解除条件。

## 8. 执行边界与隔离
- 不可信的仓库、构建脚本、安装钩子和原作客户端默认不执行。需要执行时：
  - 在隔离环境中运行，例如虚拟机、容器或无凭据的临时用户，必要时断网；
  - 安装依赖时禁用安装脚本（例如 `npm install --ignore-scripts`）；
  - 不把令牌、SSH 密钥和云凭据暴露给研究环境。
  在 REUSE.json 中为每个外部模块记录 `execution`（never / sandboxed / reviewed）和 `execution_note`。外部模块缺少这项记录时，`validate` 会提示。
- 研究材料放在 `research-private/` 或 QUARANTINE 模块的 `research_paths` 中，不进入 Git。核心路径不能位于其中，Creator 测试配置的内容也不能来自这些位置；商业代码只能来自 KEEP/ADAPT 模块；测试素材必须是原创的，或者许可清楚。

## 9. 防护能力核对
| 要求 | 支持方式 |
|---|---|
| 测试结果绑定代码版本 | 条目记录 Base 版本、代码指纹和 HEAD；Creator 测试配置记录核心指纹 |
| 关键修改后相关门禁失效 | 指纹变化使条目和测试配置过期；Base 升版本后旧版本的验证不再计入 |
| 测试历史保留 | 证据按时间戳另存；HISTORY 只追加；validate 检测删改 |
| 工具超时与挂起检测 | `timeout_min` + STALLED 警告 |
| 中断恢复 | checkpoint / resume / `task recover` / handoff |
| 不可信仓库与构建脚本 | REUSE `execution` 记录 + 本节规则（工具本身从不执行外部代码） |
| 研究、商业代码与资产来源隔离 | QUARANTINE 不得进入核心或测试配置；REUSE 只能来自 KEEP/ADAPT；三项权利记录分开 |
| 交付物就是被测试的版本 | 首次使用克隆已提交的 HEAD；核心/starter 未提交改动阻止创作者等级 |
| 停止时不夸大 | `stop --status TARGET_REACHED` 由证据核对；其他停止状态必须写原因 |
| 共享记录不含本机信息 | `validate` 拒绝 `re/` 记录中的本机绝对路径；本机信息只写 `.production/local/` |

## 10. 权限
默认允许项目内的开发、测试、本地构建和本地提交。未经授权不 push、不付费、不公开部署、不删除无关文件、不提交研究原件、不绕过登录、付费或访问限制。
