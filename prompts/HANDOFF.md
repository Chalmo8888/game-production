# 交接到其他 Agent、设备或会话

```text
请按照当前项目中的 Game Production Skill，在安全的检查点结束当前工作，并准备交接。

完成当前可以安全结束的操作后保存检查点，不再接新的写入任务。不覆盖或提交无关的改动，
不停止其他项目的服务。

1. 阅读 references/CROSS_DEVICE.md。
2. 更新工作区的 .production/HANDOFF.md：授权范围、焦点（研究 / Base / 游戏 / 阶段 / 任务）、
   各 Base 的版本与就绪度、各游戏的阶段与就绪度、需要回归的依赖、最新提交与未提交差异、
   外部阻断。
3. 对每款正在进行的游戏，更新 games/<id>/.production/HANDOFF.md 和 GAME.json：当前阶段、
   assignment、next_action（第一项下一步工作及确切的运行/验证命令）、具体缺陷、
   未通过/未验证的门禁、资产同步清单（未进 Git 的授权资产及其哈希）。
4. 运行 project.py handoff --game <id> --check，结果为 COMPLETE 后，用
   project.py run --status HANDOFF_READY（或 USER_PAUSED / RUNTIME_LIMIT，并附真实原因）记录状态。
5. 只有明确获得授权的私有仓库和分支才自动同步；没有授权时，准备一份经过检查的可移交文件清单
   或快照，不上传参考原件或密钥。

新的 Agent 应该只靠仓库和这些交接文件就能开始工作，不需要完整的聊天记录。
不要把阶段交接写成全项目最终完成，也不要声称交接后仍在后台工作。
```
