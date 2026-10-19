# 可复用代码评估规范（E1，门禁 RE01）

工程风险控制规则，不是法律意见。

## 1. 决策顺序
1. **KEEP**：有明确许可（开源许可证、自有代码、书面授权）且质量足够的成熟代码，直接进入 Base。优先选这条路线，不为了“自己写”而重写成熟系统。
2. **ADAPT**：许可允许修改；适配接口、修复缺陷、去掉耦合。保留上游关系和修改记录（LGPL 等许可证的要求）。
3. **REPLACE**：可以用但不合适（质量、性能、平台），由独立实现替换。
4. **QUARANTINE**：没有使用权利（例如反编译的原作代码、原作资源）。只放在被忽略的 `research-private/` 中做研究，不得进入 Base 核心路径，也不能作为实现来源；可以作为 `research_basis` 被引用。
5. **REVIEW**：证据不足。RE01 通过前必须全部解决。

“能复用的优先复用，不能复用的才独立实现，已有能力不足的要优化”。三条路线都要记录在 PARITY 条目的 `approach` 中：REUSE、ADAPT、REIMPLEMENT、IMPROVE。

## 2. REUSE.json 字段
`id`、`name`、`origin`（URL 或路径）、`source_kind`（original_decompiled / original_source / open_source / own_code / third_party_library / generated）、`license`、`decision`、`license_evidence`（许可文件路径和 SHA-256）、`base_paths`（在 Base 中的位置）、`research_paths`（隔离材料的位置）、`rights_basis`（例外授权说明）、`notes`、`history`。

工具强制检查：
- KEEP/ADAPT 必须有已知许可、许可证据文件和 base_paths。
- `original_decompiled` 只能在有 `rights_basis`（权利人书面授权）时 KEEP/ADAPT，否则必须 QUARANTINE 并独立实现。
- QUARANTINE 不得有 base_paths，research_paths 不得与 core_paths 重叠。
- PARITY 条目的 `reuse_modules` 只能引用 KEEP/ADAPT 模块（REUSE 只能引用 KEEP）。

## 3. 必须分开记录的对象
引擎与核心代码、工具与脚本、测试、数据表与关卡、动画数据、图像、音频、字体、文本、品牌名称、第三方依赖。运行时可以替换图片，不代表代码已经清权；AI 自己写的代码也可能直接搬用了原实现，需要检查。

## 4. 独立实现的边界
- 读过反编译代码的同一个 Agent 也可以独立实现，但必须如实声明“不是严格洁净室”。需要严格洁净室时，必须有真实的访问隔离、独立的实施者和过程记录。
- 从隔离材料中只提炼通用规则、数值意图和行为需求（写进 PARITY 的 original 和 dynamic_gap），不翻译、不逐行改写、不改名后搬用。
- 不能因为部分代码有问题就丢掉整个项目；也不能因为“GitHub 上公开”就认定可以商用。

## 5. RE01 通过条件
REUSE.json 覆盖参考对象的全部主要模块和所有第三方依赖；没有 REVIEW 项；KEEP/ADAPT 的证据有效；QUARANTINE 已经隔离；审查记录作为证据文件（`gre.py gate --id RE01 --status PASS ...`）。RE01 是 LOGIC_READY 的前提，但它**不是**商业许可，商业许可由 RE02 记录（只接受外部批准）。
