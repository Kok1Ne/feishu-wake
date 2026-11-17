# 实际代码核查记录

核查日期：2026-11-17。下载了以下三个公开仓库的源代码归档，并读取相关源码及可获得的许可证。没有仅凭 README 判定其功能已验证；没有将这些仓库的代码复制入本工程。

| 仓库 | 实际检查的文件 | 发现与取舍 |
|---|---|---|
| [ProxyAI](https://github.com/ahmadmustafa02/ProxyAI) | `android/app/src/main/kotlin/com/example/online_class_agent/WakeAndOpenActivity.kt`、`ScheduleCheckerReceiver.kt`、Manifest | 有全屏通知、亮屏 Activity、Keyguard 和 WakeLock。取消解锁后仍安排启动，4 秒超时也继续启动；调度接收器还有每分钟重新检查路径。没有找到许可证文件，GitHub license 元数据为 null；不复制其代码。 |
| [Observer Effect](https://github.com/tstromberg/observer-effect) | `app/src/main/kotlin/com/observer/effect/LauncherActivity.kt`、Manifest | 有短时屏幕锁、官方亮屏接口和 Keyguard 回调；`onDismissError` 仍启动目标，因此不照搬该错误分支。源码采用 Apache-2.0。未引入摄像头、传感器或持续检测服务。 |
| [Cue](https://github.com/Rujul-Rumale/Cue) | `triggers/time/TimeProvider.kt`、`core/TimeSchedule.kt`、`automation/boot/BootReceiver.kt` | 一次性闹钟、星期计算、取消/恢复机制可参考。它依赖整套引擎与服务，且在缺乏精确权限时退化为非精确闹钟；本项目不静默将非精确定时当作精确成功。源码采用 MIT。 |

本工程采用独立实现：先请求亮屏，再检查非安全锁屏并等待解除成功，最后发送目标启动 Intent；不在解锁失败后继续伪报成功。无障碍手势和窗口事件监听保留为经过真机失败证据后才评估的备选，未加入当前权限清单。

Android 官方依据：

- [后台 Activity 启动限制](https://developer.android.com/guide/components/activities/background-starts)
- [精确闹钟与 Doze](https://developer.android.com/develop/background-work/services/alarms)
- [KeyguardManager](https://developer.android.com/reference/android/app/KeyguardManager)
- [Full-screen Intent 行为](https://developer.android.com/reference/android/app/Notification.Builder#setFullScreenIntent(android.app.PendingIntent,%20boolean))
- [Android Emulator 硬件加速](https://developer.android.com/studio/run/emulator-acceleration)
- [官方 Emulator 历史版本](https://developer.android.com/studio/emulator_archive)
- [realme 官方后台/自启动配置指引](https://www.realme.com/bd/support/kw/doc/2134413)

这些文档说明 API 和系统行为，不构成本工程在 realme 真机上通过验收的证据。
