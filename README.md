# Feishu Wake

原生 Kotlin Android 工具：按选定星期及多个时间唤醒屏幕、解除非安全滑动锁屏并打开飞书。目标设备为 realme GT 大师探索版 / realme UI 2.0 / Android 11。

## 正式版本 1.0.0

[云端验收与签名包复测均通过](reports/CLOUD_STATUS.md)，构建源码为 `0093293c1f29287012f41281b836e72308f04872`。[正式交付产物](https://github.com/Kok1Ne/feishu-wake/actions/runs/44051893821/artifacts/14313828841) 包含 APK、源码及全部报告。realme 真机兼容性仍待首次安装验收。

## 使用

请使用通过云端门槛后生成的正式签名 APK。首次安装先完成一次 15 秒延迟息屏测试，确认飞书真正进入前台，再打开长期定时。详细步骤见 [中文使用说明](docs/USER_GUIDE_ZH.md)。

本应用不联网、不读取飞书内容、不点击考勤、不模拟定位。前台启动不代表打卡成功。默认不需要无障碍服务；可选使用情况访问只辅助核实前台事件。安全密码锁屏不会被绕过。

## 云端验证与发布

仓库为公开仓库，使用标准 GitHub 托管 ubuntu-24.04 运行器。JDK、Android SDK、KVM 和 API 30 模拟器均在临时云端运行器中使用，不要求用户电脑安装开发环境。

- Android 11 acceptance 工作流：真实官方飞书 + 独立测试夹具；收集 ADB、Logcat、Instrumentation、JVM 测试及 lint 报告。
- Android 11 verified Release 工作流：必须输入同一源码提交已经成功的完整验收运行编号，验证报告归属与摘要后才能签名编译。正式 APK 在新的 API 30 模拟器中通过实际界面复测及覆盖安装恢复，随后才导出交付物。
- 正式包名固定为 `dev.feishuwake`。密钥由 GitHub Secrets 私密保存；仓库仅记录公钥证书摘要及恢复代码。不能用新密钥替换已有密钥。
- 测试原始证据和最终结果以具体运行产物为准；仓库中的旧日期报告是历史记录，不是当前版本成功声明。

固定定时使用系统可见的 `setAlarmClock`，避免普通闹钟被待机配额延后；状态栏可能显示下一次闹钟。15 秒手动测试使用 `setExactAndAllowWhileIdle`。手机亮屏且已解锁时，全屏通知可能只显示横幅，需要点按。

## 验证边界

真实飞书前台由云端 ADB 独立观察，但没有登录账号或验证考勤。强制 Doze 不是自然长时间待机。realme 厂商冻结、自启动和锁屏策略仍待指定真机首次安装验收；详见 [待真机验证事项](reports/REALME_COMPATIBILITY.md)。

源代码为 Android Studio 工程，依赖 Gradle 8.9、JDK 17、compileSdk 35；API 30 是当前验证范围。研究项目及许可证核查见 [REFERENCES.md](REFERENCES.md)，没有复制无许可证项目代码。
