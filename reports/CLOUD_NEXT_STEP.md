# 下一步：迁移到支持硬件加速的云端测试环境

日期：2026-11-17。状态：已准备工作流，尚未在 GitHub Actions 运行。

## 已准备的入口

`.github/workflows/android11-core.yml` 使用 GitHub 托管的 Ubuntu 24.04 环境、JDK 17、API 30 x86_64 AVD。先检查 KVM 设备，再编译、运行 JVM 单元测试和 Android Lint；模拟器开机后运行现有 P0/P1 初步探测与一个 Instrumentation 配置/取消测试。

四个外部 Action 都固定到从各自官方仓库核实的提交。工作流仅允许手动触发，最长运行 35 分钟，不配置付费的大型运行器。是否有免费额度、是否允许 Actions、以及触发权限须在连接账户后确认；不承诺账户免费额度足够。

本次只添加工作流、证据收集脚本、跨平台换行配置，以及测试脚本的日志目录参数；没有修改 Android 应用逻辑。没有新增模拟器测试通过项。

## 连接后的操作顺序

1. 在 ChatGPT 中安装并连接 GitHub，选定用于此工程的私有仓库。只需授权相关仓库；不要在聊天中粘贴令牌或密码。
2. 确认仓库写入和 Actions 运行能力、账户额度，然后将工程根目录的内容提交到仓库根目录。不要把整个工作目录、SDK、构建缓存或签名私钥上传。
3. 手动触发 `Android 11 core probe (not release)`，先验证云端模拟器确实能启动，并读回该次运行的证据。
4. 根据真实运行结果修复核心流程；补充独立的屏幕/锁屏状态断言，完成真正飞书客户端的安装和前台测试。夹具成功不代表飞书成功。
5. 通过核心流程后，完成定时管理界面和 Doze、重启、进程回收、强制停止恢复、多星期、多时段、关闭与重新开启等验收矩阵。强制停止后需要重新打开应用是系统边界，不应报告成可自动绕过。
6. 所有发布门槛满足后才生成固定签名的 Release APK，并交付 SHA-256、签名验证、构建/静态/模拟器日志、源码和说明。

## 证据边界

工作流只上传本次日志、JVM 测试报告与 Lint 报告；内部 Debug APK 留在临时运行器中，不作为交付附件。该工作流不配置签名密钥，不执行 Release，不修改 `release_gate.py`。

`tools/ci_android11.py` 在模拟器退出前收集 ADB、Logcat、Activity、Power、Window、Alarm、DeviceIdle、Notification 状态，并记录 Git 提交、运行编号和日志摘要。核心探测自身结果明确标为部分测试，`release_eligible=false`。工作流绿色只能说明这些初步探测结束，不能等同于完整功能验收。

GitHub 运行器是原生 Android 模拟器，不能替代 realme UI 2.0 的厂商行为验证。最终仍须在用户手机首次正式安装后完成一次手动全流程；不能事先保证厂商限制全部兼容。

## 官方依据

- GitHub：Linux 托管运行器支持 Android 硬件加速：
  https://github.blog/changelog/2024-04-02-github-actions-hardware-accelerated-android-virtualization-now-available/
- Android Emulator Runner 的 API、架构和硬件加速配置：
  https://github.com/ReactiveCircus/android-emulator-runner
- Android 官方模拟器加速说明：
  https://developer.android.com/studio/run/emulator-acceleration

这些资料说明迁移路线具有依据，不构成本项目已在该环境运行成功的证据。
