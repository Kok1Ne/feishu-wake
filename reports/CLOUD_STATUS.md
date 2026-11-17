# 云端验证状态

更新：2026-11-17（北京时间）。

- 仓库已按用户要求公开：https://github.com/Kok1Ne/feishu-wake 。
- 使用 GitHub 托管的标准 Ubuntu 24.04 运行器；SDK、编译和模拟器只在云端运行。
- 与本地 Windows 环境的历史结果分开记录；不再在用户电脑安装或运行 Android 工具。
- 公开仓库的标准运行器计算不扣私有仓库包含额度。依据：https://docs.github.com/en/billing/concepts/product-billing/github-actions 。

## 已实际运行

| 运行 | 提交 | 结果 |
|---|---|---|
| [1](https://github.com/Kok1Ne/feishu-wake/actions/runs/44032716240) | b7f662c | sdkmanager 不在 PATH，已补 SDK 初始化 |
| [2](https://github.com/Kok1Ne/feishu-wake/actions/runs/44033067471) | cc4f756 | SDK 初始化引用已退役的 tools 包，已改为 platform-tools |
| [3](https://github.com/Kok1Ne/feishu-wake/actions/runs/44033270243) | 6242c9c | JDK/KVM、SDK、编译、JVM 测试、Lint 步骤通过；模拟器未启动：云端剩余 7276.84 MB，创建 userdata 需要 7372.80 MB |

运行 3 的模拟器启动失败，未执行设备内测试，不能作为功能通过的证据。本次修复仅清理临时云端运行器中不使用的 NDK/CMake，并增加息屏、滑动锁屏、前台状态及解锁与启动顺序的独立断言；修复后的结果以新运行证据为准。

## 仍未达到交付门槛

当前没有 Release APK。真实飞书前台、Doze、重启恢复、多任务、关闭取消和 realme UI 2.0 真机行为仍需验证。测试夹具不是飞书客户端。realme 厂商行为必须由最终真机验收确认。

代码或测试脚本修改会自动运行此云端检查，也保留手动运行入口。只上传报告和日志，不向用户交付开发 APK，也不包含签名密钥。
