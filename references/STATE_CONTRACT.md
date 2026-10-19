# 项目状态与最少记录

## 位置
Skill 目录是可复用规则；游戏 `.production/` 是本项目事实。不把项目进度写回共用 Skill 模板，也不把模板全拷到根目录污染原项目。

日常最少维护：
- PROJECT.json：目标、范围、权限、交付合同及其版本。用户定方向，Agent 从已有资料补细节；不得静默下调。
- STATE.json：运行模式、允许阶段、当前任务、真实停止原因和简短接续状态。
- BACKLOG.md：任务、依赖、优先级、阶段/文件归属、验证方式、完成证据。
- GATES.json：门禁状态唯一来源，不在多个 Markdown 里重复维护不同答案。
- HANDOFF.md：给下一会话的短摘要，不再写一篇从头研究历史。
- RIGHTS_LEDGER.md：复用、替换、隔离依据。审计通过不是授权证书。

`.production/local/ENVIRONMENT.json` 仅本机：绝对路径、工具存在性、版本、端口、缓存/预算能力，不含真实密钥；不提交 Git。共享文件只保存项目相对位置、允许的公共来源与非敏感信息。

按需生成 MECHANICS_MATRIX.md、ASSET_CONTRACT.md、REVIEW.md 和 evidence/。不用一次填完十几份空表。

## 运行与项目状态不同
PROJECT.delivery_target：release_candidate、mechanics_handoff、research_handoff、creator_base（可按未来版本扩展，目前 CLI 支持这四类）。
STATE.run.mode：auto、stage、review。
STATE.run.allowed_stages：本次允许做的阶段；默认 S0–S6。
STATE.run.status：NEW、RUNNING、TARGET_REACHED、HANDOFF_READY、EXTERNAL_BLOCKED、RUNTIME_LIMIT、USER_PAUSED。
STATE.publication_status：NOT_AUTHORIZED、REVIEW_PENDING、AUTHORIZED_NOT_PUBLISHED、PUBLISHED。只有授权/平台证据才能改变，不由本地测试自动推进。

典型：一个 Agent 只做 S4，结束为 HANDOFF_READY；项目仍是 release_candidate 目标，不可改为“资产做了一半就算完”。

## 门禁 JSON 结构
每项含 id、name、criteria、status、required_for_target、scope_basis、reviewer、subject_revision、evidence、blocker、next_action。
PASS 必须有具体 criteria、subject_revision 和非空 evidence。每个 evidence 包含项目内相对 path、文件 SHA-256、kind、观察摘要 observed。引用文件必须可核验；不要放本机 E 盘绝对路径。
NOT_APPLICABLE 必须带 scope_basis，表示不在需求范围，不表示没有工具。需要外部审查的 G10 可以在候选阶段未通过，但发布仍为未授权。

## 工具职责
`project.py init`：安装 Skill 副本、缺少的状态模板、AGENTS 引导块和本地忽略规则。已有内容不覆盖；同名 Skill 内容不一致时拒绝自动升级。
`project.py validate`：检查格式、状态、证据文件与哈希。它不运行游戏测试、不解析法律、不判断截图品质。默认允许未验证项目通过“结构检查”；`--strict-target` 才会要求已定义合同和目标适用门禁 PASS。该命令通过仍不是公开发行许可。
`project.py handoff`：只输出当前记录摘要和 Git 状态给 Agent 参考；不自动提交或替代实机复核。

## 版本升级
新规则不覆盖已有游戏数据、任务、来源记录。变更目标或门禁需留版本/原因；已验收证据视变更影响局部失效，而非一键全绿。规则版本和状态 schema 分开管理。
