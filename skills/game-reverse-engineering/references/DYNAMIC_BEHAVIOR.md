# 原版动态行为研究规范（E2）

静态代码说明的是“可能发生什么”，动态观测说明的是“实际发生了什么”。手感、时序、动画和特效几乎都需要动态证据。

## 1. 第 0 天的运行尝试
按顺序尝试，并记录在 `re/DYNAMIC_STUDY.md` §1：
1. 官方或原生运行环境（原版客户端、浏览器、移动端）。
2. 模拟器或播放器（例如 Flash 内容使用的开源播放器），以及不同版本或配置。
3. 开源移植或重制版作为代理（证据等级最多为 PROXY）。
4. 公开录像、社区数据（证据等级 INFERRED，需要多个来源交叉印证）。

每种方法设时间盒。全部失败时，把阻断写进 TECH_SURVEY 和 BASE_HANDOFF，并继续其他可执行的工作。不得无限期地卡在“让原作跑起来”上。

## 2. 观测方法
| 对象 | 方法 | 证据类型（kind） |
|---|---|---|
| 移动、跳跃、加速度、碰撞 | 固定帧率录屏逐帧测量位置；输入回放 | measurement / recording |
| 攻击前摇、命中帧、硬直、冷却 | 逐帧计数，与输入时间对齐 | measurement |
| AI 状态与 Boss 阶段 | 多次录像对比，记录触发条件 | recording / comparison |
| 数值（伤害、血量、经济） | 日志、内存读取或可控实验 | trace / measurement |
| 动画帧数、部件结构、挂点 | 逐帧截图、轮廓叠加 | runtime-capture / measurement |
| 图层、遮挡、排序 | 构造重叠场景截图 | runtime-capture |
| 特效与粒子 | 录像逐帧，统计数量与生命周期 | recording / measurement |
| 音效与帧事件 | 音频波形与帧序列对齐 | measurement |

记录数值时附带单位、帧率、样本数和误差。用 `gre.py parity set --item <id> --original-level VERIFIED --original-ref <文件> --ref-kind measurement` 写入条目；只在本机保存的大文件加 `--ref-local`。

## 3. 只有静态证据时
- 条目标为 STATIC_ONLY（或 INFERRED / PROXY），并写 `dynamic_gap`：缺少什么确认、对 Base 有什么影响、以后如何补证（工具会强制要求）。
- 手感类参数可以先给出可调的配置，并在 differences 中写明“未与原版动态对照”。
- 不得把“符号名存在”或“函数存在”写成“行为已验证”。
- 报告会列出所有静态条目，交付时要如实说明。

## 4. 与 Base 验证的对照
原版动态证据与 Base 自身的运行时证据应当可以对照：同一场景、同一输入，比较不含渲染细节的状态摘要，或者对比测量值。对照结果作为 `comparison` 证据加入条目的 verification。

## 5. 证据管理
- 原始录像和转储放在 `research-private/`（不进 Git）；可以共享的摘要、测量表和截图放在 `re/evidence/`，用 `gre.py evidence` 按时间戳存入，不覆盖旧文件。
- 不上传原作资源，不在共享记录中写设备绝对路径。
