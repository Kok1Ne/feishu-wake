# 云端状态（2026-11-17，正式包已完成）

仓库已改为公开。构建和模拟器测试在标准 GitHub Actions Ubuntu 云端运行器执行，未在用户电脑安装或运行 Android 开发工具。

## 本次正式版本

- 版本 1.0.0；固定包名 `dev.feishuwake`。
- 构建与测试源码：`0093293c1f29287012f41281b836e72308f04872`。后续文档更新不改变该 APK 的源码归属。
- [完整 Android 11 验收](https://github.com/Kok1Ne/feishu-wake/actions/runs/44048061951)：成功；真实飞书 126 个检查点、测试夹具 11 个检查点通过。包括异常拒绝与边界分类，不能解读为所有屏幕状态均自动启动成功。
- JVM 单元测试 11 个通过；Instrumentation 两个测试在真实飞书与夹具两轮各运行一次，两轮均 OK (2 tests)。
- [正式签名包构建及复测](https://github.com/Kok1Ne/feishu-wake/actions/runs/44051893821)：成功；全新 API 30 模拟器的 16 个正式包检查点通过，包括实际界面延迟测试、解锁后真实飞书稳定前台、覆盖安装与任务恢复。
- Gradle Release：BUILD SUCCESSFUL。Release lint：0 Error / Fatal，7 Warning（目标 SDK 非最新、测试依赖新版、Android 12+ 备份规则及中文国际化提示），完整 XML/HTML 报告保留在产物中。
- apksigner：Verifies；APK Signature Scheme v2 验证通过。
- APK SHA-256：`f9d7b8e6f52a09a51c21ca74b0a09159ddd7975f759c69426b3e9641fac3f759`。
- 固定证书 SHA-256：`323c450b86e5e0439bd0928e7ad574daa08fe2e5b66c13ea68aa9fe2cba96a45`。密钥仅存于私密 Secrets 及用户私密恢复资料，未公开。
- [完整原始交付产物](https://github.com/Kok1Ne/feishu-wake/actions/runs/44051893821/artifacts/14313828841)：APK、完整 Android Studio 工程、签名、哈希、中文使用说明、云端报告、ADB/Logcat/Instrumentation/静态检查原始证据。Actions 产物保留至 2026-12-01，另已向用户交付保存版本。

## 准确的验证边界

- 飞书来自官方渠道，云端核验安装包身份与签名，ADB 独立确认实际前台；未登录账号、未操作或核验考勤。
- 息屏、非安全滑动锁屏流程通过。亮屏且已解锁时观察到仅通知横幅，需要点按；这是明确限制，不是自动前台成功。
- 强制 Doze 测试通过，不等于自然长时间待机。固定时刻采用系统可见的一次性 setAlarmClock，手动测试采用 setExactAndAllowWhileIdle。
- 重启测试中 adb reboot 导致云端模拟器宿主进程退出；脚本冷启动同一 AVD，未清空数据、未重装或手动打开应用。核验 kernel boot_id 改变、BOOT_COMPLETED、原配置和未来闹钟恢复及实际执行，属于保留数据的模拟器冷启动恢复。
- realme GT 大师探索版 / realme UI 2.0 真机尚未测试。厂商后台冻结、自启动、电池策略及锁屏差异仍需首次正式安装后的单次验收。
- 强制停止后系统取消任务，用户重新打开应用后恢复。不会绕过安全密码。

## 历史问题与修复

第 6 轮核心流程通过。第 7–9 轮扩展矩阵暴露普通精确闹钟重启后延后、测试准备的电源/锁屏时序，以及模拟器宿主重启行为；原始失败报告保留。固定调度改为 setAlarmClock，测试准备等待稳定电源状态，重启依据内核身份及保留数据验证；第 10 轮完整验收及正式包复测均成功。旧日期报告是历史记录，不代表当前状态。
