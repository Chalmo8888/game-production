# 发行候选清单（G6）

门禁状态唯一来源是 `.production/GATES.json`（R01–R04）。本清单帮助逐项执行，不代替证据。

## 构建（R01）
- [ ] 从干净检出构建，记录命令、提交和环境
- [ ] 产物 SHA-256 写入 GAME.json `release`
- [ ] 必需资源全部在包内，无静默占位回退
- [ ] 包内无研究原件、反编译代码、密钥、私有路径、调试作弊接口
- [ ] 许可证要求附带的声明/源码随包提供

## 平台（R02）
- [ ] 目标平台规范来源与版本（未知则写待适配，不猜字段）
- [ ] 入口、相对路径、存档作用域、SDK/manifest 实测

## 权利（R03）
- [ ] 绑定 Base 版本创作交接中的权利状态：RE01（代码与组件许可）PASS，RE03（原版资产/表达）PASS 或 NOT_APPLICABLE
- [ ] 本游戏资产/音频/字体/文本来源（Q08、RIGHTS_LEDGER、ASSETS.json）
- [ ] 待权利人/法务确认事项列表

## 发布批准（R04）
- [ ] 用户/权利人书面批准记录（evidence 文件 + SHA-256），reviewer.independence = external_approval
- [ ] 未获批准时 publication_status 保持 NOT_AUTHORIZED 或 REVIEW_PENDING
