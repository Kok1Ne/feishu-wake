# Feishu Wake 实际验证报告

> 后续排查已补充虚拟化状态、原生崩溃与 ARM 尝试，见 [EMULATOR_FOLLOWUP.md](EMULATOR_FOLLOWUP.md)。功能验证仍未通过。

记录时间：2026-11-17T13:59:31+08:00（北京时间）

**结论：尚未确认功能可正常实现，未达到正式包交付门槛，没有生成 Release APK。**

当前已完成可编译的核心验证程序和内部测试工具。Android 11 模拟器在系统启动前退出，因此没有完成实际安装、亮屏、解锁和飞书前台测试。不能将下面的编译、JVM 测试或静态分析结果解释为 Android 功能已通过。

## 环境实际检查

| 项目 | 实际状态 |
|---|---|
| 执行环境 | Windows 10 工作区；并非另有一台已配置的云端 Android 测试机 |
| 初始 Java | 仅找到 Java 8 JRE；未找到原有 JDK/Android SDK/Gradle/Emulator |
| 已补齐 JDK | Amazon Corretto 17.0.21，java/javac 可执行 |
| Android SDK | Platform 30 与 35、Build Tools 35.0.0、命令行工具 |
| Gradle | 8.9；Wrapper 校验值与官方分发包一致 |
| ADB | 1.0.41，Platform Tools 37.0.1；本任务使用独立端口 5041 |
| API 30 镜像 | AOSP Android 11，x86_64 revision 11，下载归档校验通过 |
| 硬件加速 | `emulator -accel-check` 返回 6，并提示未安装 Android Emulator hypervisor driver |
| 固件虚拟化开关 | WMI 查询被拒绝，不能据此判断 BIOS 中是否启用；未修改系统驱动/虚拟化设置 |
| 软件模拟 | Emulator 37.2.13 与 35.2.10 均尝试无窗口、无硬件加速启动 |
| 启动结果 | 两个版本的已记录尝试均在约 4 秒后以 `0xFFFF7001` 退出；`sys.boot_completed=1` 未获得 |
| ADB 设备 | 任务专用 ADB 设备列表为空 |

退出码是实际观测，模拟器崩溃根因尚未确定。不能把“缺少硬件加速”直接说成该崩溃的已证实唯一原因。未使用管理员权限更改系统配置。

## 已实际执行的检查

| 检查 | 结果 | 证据 |
|---|---|---|
| 主应用 Debug 编译 | PASS | `gradle-build.log`，BUILD SUCCESSFUL |
| 测试目标应用编译 | PASS | `:testtarget:assembleDebug` |
| Instrumentation 测试 APK 编译 | PASS | `:app:assembleDebugAndroidTest`，仅编译，没有运行 |
| JVM 调度测试 | 11 项，失败 0，错误 0，跳过 0 | `unit-tests.xml` |
| Android Lint | 错误 0，警告 7 | `lint-results-debug.xml/html` |
| Release 拦截检查 | PASS：缺少功能验证证据时拒绝发布 | `release-gate.log` |
| 宿主测试脚本预检 | BLOCKED：模拟器设备不存在 | `android-host.log` / `android-host-results.json` |

单元测试覆盖：工作日早晚、精确时刻不重复、跨周、关闭状态、非法配置、重复时间、已执行时间去重、周日组合、夏令时跳时/回拨。它们没有测试 Android 平台权限、Doze 或锁屏。

Lint 警告包括固定依赖存在更新、仅 Debug 使用的导出控制 Receiver、备份规则提示和中文界面字符串提示；没有将警告描述成零问题。Debug 控制 Receiver 位于 `src/debug`，不会进入 Release。

## 尚未运行的功能矩阵

| 项目 | 状态 |
|---|---|
| APK 在 Android 11 中安装、启动 | NOT RUN |
| 息屏时 Alarm 触发、屏幕自动点亮 | NOT RUN |
| 非安全滑动锁屏解除 / 安全锁屏拒绝 | NOT RUN |
| A/B 两条唤醒路线比较 | NOT RUN |
| 真实飞书进入前台、已有任务复用 | NOT RUN |
| 测试夹具进入前台 | NOT RUN |
| Doze、充电/不充电、亮屏已解锁 | NOT RUN |
| 重启恢复、普通进程回收、强制停止后恢复 | NOT RUN |
| 多时间、关闭/开启、修改时间取消旧闹钟 | Android 层 NOT RUN；仅部分纯计算逻辑有 JVM 测试 |
| 通知拒绝、全屏通知受限、异常解锁 | NOT RUN |
| realme UI 2.0 所有机型特有行为 | NOT RUN |
| 连续多天稳定性 | NOT RUN |

没有生成伪造的 Logcat、前台截图或真机测试结果。没有安装/登录飞书，没有访问用户手机，没有要求用户重复安装测试包。

## 发布状态与后续条件

- 正式包名已固定为 `dev.feishuwake`；正式签名密钥尚未生成。
- Release APK、Release SHA-256、正式签名验证结果：**均不存在 / 不适用**。
- 内部 Debug APK 仅用于开发构建验证，没有包含在交付归档中，也不能作为成品安装建议。
- P0/P1 功能实测必须在可成功启动的 API 30 环境中继续，真实飞书与测试夹具的结果必须分别记录。
- 核心流程通过后再补全定时管理界面与全部平台矩阵；通过云端验证后才可签名生成成品，再进行一次目标真机首次安装验收。
- 当前没有可用的远程测试设备。后续需要可运行 Android 11 的模拟器或测试环境；源码和证据可继续使用，不必从头开发。

当前源码摘要（不含报告、构建产物及密钥）：`c4064c484c18c071afb3fe1726197a9ef6322dc3bf946a3db935ea43d04728b2`。
