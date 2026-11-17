# 第 7 次云端验收：未通过

实际运行：https://github.com/Kok1Ne/feishu-wake/actions/runs/44037848836

源码：0fee3209d19a7c555688eae01df3c7d2334005b1。Gradle、11 个 JVM 测试与 lint 通过；Android 11 / API 30 Google APIs 模拟器实际启动，真实飞书参与测试。未生成 Release APK。

已通过：息屏触发、点亮、解除滑动锁屏、真实飞书前台、安全密码拒绝、取消待执行测试、进程回收、多时段、取消旧时间、重新开启、强制停止后重新打开恢复。

发现与处理：

- 重启：BOOT_COMPLETED 于 07:33:53 UTC 实际收到。脚本提前 6 秒取样误判未恢复；但闹钟本身也确实未准时执行。dumpsys 显示 expectedWhenElapsed 已过期约 49 秒，而 whenElapsed 被延后到约 24 小时后。第 8 次将固定时间改为用户可见的 setAlarmClock，并等待恢复状态真正落盘；不是把此项修改为静态通过。
- Doze：观察到深度 IDLE，闹钟及真实飞书前台通过；初始锁屏取样仍在 GOING_TO_SLEEP，不能算完整锁屏 Doze 通过。改为有限等待锁屏状态稳定再取证。
- 通知关闭：POST_NOTIFICATION AppOps 修改未真正关闭系统通知设置，飞书仍成功启动。改用模拟器的系统通知设置主开关并验证其状态。
- 取消状态：XML 空字符串被脚本解析为 None；修正解析，不改动应用取消逻辑。
- UI 总开关：测试线程在 enabled=false 已保存、cancel 尚未完成时立即断言 nextDue=0。改为同时等待开关关闭、nextDue 清零和 token 清空。

固定时间采用系统可见闹钟的代价：系统可能展示下一次闹钟；系统会为准点执行退出低功耗状态。15 秒手动测试保留 setExactAndAllowWhileIdle，用于单次唤醒流程及强制 Doze 的独立验证。自然长时间待机与 realme 厂商策略仍未验证。

Android 官方接口说明：https://developer.android.com/develop/background-work/services/alarms

原始证据 Artifact 14308659021，ZIP SHA-256：4b568d480d87d9d3d16285bb1f1cf9f95fe0545fe4cf142178a3e2861ed6f0c4。
