# Feishu Wake — 开发验证检查点

当前不是最终成品，也没有随此工程交付测试 APK。

本项目的后续依赖安装、编译和模拟器测试只在 GitHub Actions 云端运行器执行；不再在用户电脑上安装或运行 Android 开发工具。此前 Windows 记录属于历史排查，不能当作云端验证结果。当前远程仓库为 https://github.com/Kok1Ne/feishu-wake 。

目标：realme GT 大师探索版 / realme UI 2.0 / Android 11。用户设定星期和时间后，唤醒屏幕、解除非安全滑动锁屏、打开飞书。软件不执行考勤点击、不处理定位、不获取飞书内容、不联网。

## 当前实现范围

- Kotlin 原生工程，固定正式包名 `dev.feishuwake`；内部调试包名 `dev.feishuwake.debug`。
- P0/P1 最小界面：立即测试、15 秒后测试、A/B 两条定时唤醒路线、取消测试、权限入口、日志导出。
- B 路线：一次性精确闹钟 → Receiver → 短时前台服务 → 高优先级全屏通知 → WakeActivity。
- A 路线：一次性精确闹钟 → Activity PendingIntent → WakeActivity；仅用于对照测试，尚未确定最终采用哪一条。
- WakeActivity 进入 Resumed 后检查屏幕交互状态，记录 `isDeviceSecure`、`isKeyguardSecure`、`isKeyguardLocked`，再请求解除非安全锁屏。
- 只在无锁屏或系统确认解除成功后发送飞书启动 Intent。安全锁屏、解锁拒绝或超时均停止本次任务。
- 默认区分 `REQUESTED`（启动请求被接受）与 `UNKNOWN`（未核实前台）。可选使用情况访问仅提供前台事件辅助证据，不保存其他应用名称。
- 飞书包名通过 Manifest queries 声明为 `com.ss.android.lark`，通过系统 launcher Intent 复用现有任务。
- 启动目标后释放本程序页面，短时诊断结束后停止服务。屏幕超时遵循系统设置，不自动返回桌面、不主动结束飞书。
- 已有星期/多时间计算、去重、持久化、重启/时区/时间/更新恢复的基础代码与单元测试；完整定时管理界面和长期运行验收尚未完成。

## 构建

安装 JDK 17、Android SDK Platform 35、Build Tools 35.0.0；验证设备使用 API 30 镜像。

```text
gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug :app:assembleDebugAndroidTest :testtarget:assembleDebug
```

Android Studio 直接打开本目录。SDK 路径通过 `ANDROID_HOME` 或本机 `local.properties` 指定。不要将其他电脑的 SDK 路径直接照搬。

构建工具固定为 Gradle 8.9 / Android Gradle Plugin 8.7.3 / Kotlin 2.0.21；编译 SDK 和目标 SDK 为 35，最低 API 为 27。Android 12+ 的精确闹钟、Android 13+ 通知、Android 14+ 全屏通知均有显式处理，但未实测这些系统版本。

## 自动化验证

已补充 GitHub Actions 的 Android 11 云端测试入口，见 `.github/workflows/android11-core.yml` 和 [下一步说明](reports/CLOUD_NEXT_STEP.md)。该入口尚未运行，只执行部分核心探测，不会发布 APK 或解除 Release 门槛。

`app/src/test` 是 JVM 单元测试，不能验证屏幕、锁屏或后台 Activity 限制。

`app/src/androidTest` 是待运行的 Android Instrumentation 测试。`testtarget` 是独立测试夹具，名称和包名均明确区别于飞书。夹具测试即使通过，也不能作为真实飞书测试通过的证据。

启动 API 30 模拟器后可运行：

```text
python tools/verify_android.py --adb PATH_TO_ADB --serial emulator-5580 --port 5041 --target mock
```

该脚本只接受 `emulator-数字` 序列号，先检查 Android 已完成开机，再安装内部测试产物。前台验证由宿主 ADB 的 Activity 状态提供；后台启动测试期间不运行 Instrumentation，避免其权限影响测试结果。完整 Doze、重启、多任务、强制停止恢复等矩阵仍需补充并执行。

真实飞书客户端需要来自官方的安装包并在模拟器上可运行。`--target feishu` 不会自动下载、登录或操作飞书，只检查已安装目标；没有真实客户端不能标记飞书测试通过。

## 成品发布门槛

Release 任务依赖 `tools/release_gate.py`。只有当前源码摘要一致、全部必需的云端验证 PASS、原始证据文件存在且摘要一致、固定签名配置存在时才允许继续。没有证据时直接失败，不生成正式 APK。

当前未创建正式签名密钥，未生成 Release APK，因此不存在正式 APK 的 SHA-256 和签名验证结果。调试签名不能替代正式签名。正式发布时需一次性创建并单独备份长期密钥，之后所有版本复用；不得把私钥或签名密码提交到源码仓库。

## 首次安装配置草案（待成品验证后使用）

1. 安装正式包后打开一次，允许通知和“定时唤醒”通知频道的锁屏显示/弹出。
2. realme 系统设置中查找本应用的“电池使用情况/应用耗电管理”，允许后台活动、自启动及启动其他应用；不同固件的名称可能不同。可把本应用加入最近任务锁定。
3. 系统锁屏使用“滑动”，不使用密码、图案、指纹安全认证。程序不会绕过安全认证。
4. 飞书按其自身要求完成登录和极速打卡配置。
5. Android 11 不需要额外授予 Android 12 的精确闹钟特殊权限。使用情况访问是可选项，不开启时显示“前台未核实”。无障碍服务不是当前实现的必需条件，也未加入本工程。
6. 首次成品验收使用“15 秒后测试”，在倒计时期间按电源键息屏，再观察完整流程。失败时导出应用内部诊断 JSON，而不是反复卸载重装。

## 系统边界

- 手机已解锁时，全屏通知可能只显示横幅；A 路线是否可作为补充必须实测后决定。
- 免打扰、关闭通知/锁屏通知、系统后台冻结可能阻止全屏唤醒。
- 强制停止会清除闹钟并阻止后台恢复，必须重新打开应用。普通进程回收与强制停止应分别验证。
- 精确闹钟在 Doze 中仍受频率限制；不承诺密集到每分钟的后台触发。应用当前对严重迟到任务设有跳过策略。
- 模拟器不复现全部 realme 自启动、冻结、锁屏及省电行为。realme 兼容性、连续多天稳定性、充电/不充电差异尚未验证。
- 启动请求、目标前台、飞书自身完成打卡是三个不同结果。

本次验证的实际结果见 `reports/VALIDATION_REPORT.md`，以原始日志和测试结果文件为准。
