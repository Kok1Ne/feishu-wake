# Android 11 核心实验结果（2026-11-17）

运行：[44034489810](https://github.com/Kok1Ne/feishu-wake/actions/runs/44034489810)，提交 e2a809112588b0b192004c5cf602f2ab48ee3823。
证据包：[14307580296](https://github.com/Kok1Ne/feishu-wake/actions/runs/44034489810/artifacts/14307580296)，SHA-256 8c760dddd6ac08e460df48d2fa3596fa8c4fbf0684ee0f83bb7507b2853f315e。

- 云端 KVM 可用，Android 11 / API 30 已实际启动。
- B 路线：触发前 Asleep、Keyguard showing=true；闹钟触发、屏幕 Awake、解锁成功、测试夹具处于系统 Resumed Activity 均通过。
- B 的日志顺序为 trigger → screen → keyguard_request → keyguard OK → launch REQUESTED。外部 ADB 独立验证夹具前台；应用内部仍如实记录 foreground UNKNOWN。
- A 路线：AlarmManager 在到期时尝试启动 Activity，但系统记录 Background activity start、isBgStartWhitelisted=false；WakeActivity 未进入执行，设备仍息屏且锁定。此路线不能视为可用，正式调度继续采用 B。A 只保留为开发对比，不用作可靠兜底。
- 检查发现 A 的日志读取混入了 B 的历史条目，因此 A 的 unlock_before_launch 单项存在假阳性；该 A 结果作废，不影响其独立前台/亮屏失败结论。现已加入设备时间过滤，并要求所有步骤属于当前 trigger 的同一 run id。
- Android Instrumentation 的配置持久化/取消断言通过，且没有在背景启动试验期间运行 instrumentation，避免测试权限影响 BAL。
- 本轮整体为失败，不能据此交付 Release；B 的成功仅针对测试夹具，不是实际飞书或 realme 真机。

官方飞书安装包已于云端独立获取、检查，版本 8.5.4，包名 com.ss.android.lark，仅含 arm64-v8a 库。APK SHA-256 为 7298c30b3461403345b92599068d8bf5179c9f91914d558badcd853bc49c7fc7；签名校验通过，证书 SHA-256 为 d3f0e06b185518663e2afea2fcd528f5b0b8ca6c3b47e57b22893715043572ec。这是目标客户端的校验，不是本项目 Release 签名。

下一轮采用 Google APIs API 30 镜像以提供 ARM 转译，分别验证夹具及真实飞书的 B 路线；飞书未登录状态不等于考勤验证。
