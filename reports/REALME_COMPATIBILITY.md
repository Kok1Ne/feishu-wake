# realme UI 2.0 / Android 11：待真机验证事项

目标：realme GT 大师探索版。至今未连接或测试该手机，以下任何项目都不能标记为“realme 已通过”。云端 Android 11 镜像不能复现 realme 的系统管理策略。

| 项目 | 已有软件处理 | 云端可验证范围 | 真机仍需确认 |
|---|---|---|---|
| 后台 Activity 启动限制 | 使用用户设置的闹钟通知 Full-screen Intent；不把后台 startActivity 当作可靠路径 | AOSP API 30 已发现 A 路线被 BAL 限制；B 路线已在测试夹具上通过 | realme 是否另有后台弹出界面限制 |
| 全屏通知 | 高重要性闹钟渠道、权限状态提示、20 秒失败超时；总开关负责取消任务 | 通知权限/渠道限制、息屏时全屏显示可独立测试 | 厂商锁屏通知/弹出界面开关；已解锁且亮屏时通常仅显示横幅，不能据此宣称自动前台成功 |
| 滑动锁屏 | WakeActivity 可见后请求原生解锁；等待回调并复查 isKeyguardLocked | 非安全锁屏和安全 PIN 拒绝可分别测试 | realme 的回调时序或系统拒绝；不尝试绕过密码 |
| WakeLock | 短时 PARTIAL_WAKE_LOCK 保持 CPU；真正亮屏由 Activity 接口完成，完成后释放 | 原生电源状态及 Doze 可测试 | 厂商是否阻断流程、限制唤醒；不将 WakeLock 获取等同亮屏 |
| 后台冻结/电池优化 | 一次性 AlarmManager 调度，不依靠永久前台服务轮询 | 系统进程回收、Doze、AppOps 限制是原生机制测试 | 冻结后台、深度省电、应用速冻是否拦截闹钟/服务；原生测试不是这些厂商功能的替身 |
| 自启动与开机恢复 | BOOT_COMPLETED、时间/时区变化、应用更新重新安排任务 | 模拟器重启可以检查注册恢复 | realme 自启动权限是否允许接收开机广播和后续启动 |
| 强制停止 | Android 可取消闹钟，必须由用户重新打开应用恢复 | 强制停止后不执行、重新打开后恢复需真实测试 | 厂商“一键清理”是否等同强制停止，不能保证绕过 |

默认无需无障碍权限。只有最终真机证据表明原生滑动锁屏解除失败，才评估由用户主动授权的手势备选；不读取飞书内容、不截图、不点击考勤。

## 单次安装验收原则

只有云端交付门槛通过后才生成正式签名 APK。首次安装先设置系统权限并执行一次延迟手动测试：息屏 → 点亮 → 解除滑动锁屏 → 飞书前台。确认成功再开启长期定时。

应用日志必须区分启动请求已发送、前台证据和打卡结果；本应用不判断或执行打卡。失败优先导出内部日志，集中修复后才更换正式版本。

官方机制说明：
- https://developer.android.com/guide/components/activities/background-starts
- https://developer.android.com/reference/android/app/KeyguardManager
- https://developer.android.com/training/monitoring-device-state/doze-standby

本文件记录边界和验收要求，不是已完成测试的报告。
