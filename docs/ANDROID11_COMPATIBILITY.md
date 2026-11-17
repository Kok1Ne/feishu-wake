# Android 11：验证范围与设备差异

目标系统为 Android 11 / API 30。云端使用实际启动的 Google APIs 模拟器及官方飞书客户端；模拟器测试不能代替所有手机的后台、通知和电池管理策略。

| 情况 | 软件处理 | 验证与边界 |
|---|---|---|
| 通知关闭或渠道重要性不足 | 手动测试前说明原因，不注册无效测试；执行时再次检查 | 云端通过真实系统设置关闭通知验证 |
| 全屏通知未打开页面 | 分别记录通知提交、页面创建、页面前台生命周期；20 秒后明确失败 | 可控故障注入用于验证诊断，不声称复现某款手机内部策略 |
| 可选兼容唤醒 | Android 11 下用户主动启用并授权“显示在其他应用上层”，3 秒后仍未进入页面时尝试打开 WakeActivity | 默认关闭；不创建悬浮窗口、不读取页面、不截图；授权、未授权和撤权分别测试 |
| 非安全滑动锁屏 | 可见 Activity 请求系统解除，并等待成功回调或确认已无锁屏后才启动飞书 | 安全密码锁屏明确拒绝；不绕过 PIN、密码或图案 |
| CPU 与亮屏 | 短时 PARTIAL WakeLock 保持 CPU；Activity 的 setTurnScreenOn 负责亮屏 | 获取 WakeLock 不等于亮屏；仍要确认系统交互状态 |
| 后台与电池限制 | 一次性固定闹钟，短时执行服务；开机、时间变化和更新后重新安排 | 强制 Doze、进程回收、重启可以在云端测试；自然长期待机及设备冻结行为仍待确认 |
| 强行停止 | 用户重新打开应用后恢复未来任务 | Android 可取消被强行停止应用的闹钟，不能承诺自动恢复 |
| 飞书前台 | 默认只记录启动请求；可选使用情况访问辅助观察目标前台事件 | 云端另用 ADB 独立确认真实飞书前台；不登录账号、不验证或操作考勤 |

用户曾反馈 1.0.0 的通知关闭失败及唤醒页面超时。截图可定位在页面启动之前，不能唯一确定通知策略、后台限制或锁屏可见性原因。1.0.1 补充阶段日志和可选启动路径；是否解决具体手机上的失败仍以该手机测试为准。

官方机制：
- https://developer.android.com/guide/components/activities/background-starts
- https://developer.android.com/reference/android/app/Notification.Builder#setFullScreenIntent(android.app.PendingIntent,boolean)
- https://developer.android.com/reference/android/app/KeyguardManager
- https://developer.android.com/training/monitoring-device-state/doze-standby

本文件是范围说明，具体通过结果以对应版本的 CLOUD_TEST_REPORT_ZH.md 和原始日志为准。
