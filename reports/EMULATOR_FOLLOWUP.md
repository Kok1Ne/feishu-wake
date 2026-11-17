# Android 11 模拟器补充排查

日期：2026-11-17。本次没有修改应用源码，没有新增 Android 功能测试通过项，没有生成 Release APK。

模拟器与 Android 11 镜像已安装。此前失败发生在模拟器启动阶段。

1. 使用 Windows API `IsProcessorFeaturePresent` 重新检查：固件虚拟化已启用，支持二级地址转换（SLAT）。因此此前 WMI 无法读取的信息现在已由该 API 补充。
2. `WHvGetCapability(WHvCapabilityCodeHypervisorPresent)` 调用成功，返回 `hypervisor_present=false`。结合先前 `-accel-check` 结果，当前没有可用的模拟器硬件加速。
3. 新建隔离的 AVD、临时目录及配置目录，用单核、关闭 GPU、关闭快照的 Android 11 x86_64 软件模拟模式启动；约 3 秒后再次退出，没有进入 Android。
4. 对本任务自己启动的模拟器做原生异常观察，确认 QEMU 进程出现读取空地址的 `0xC0000005` 异常。它说明模拟器本体崩溃，未能确定导致该空指针的完整根因。
5. 崩溃报告组件另有明确日志：`CreateNamedPipe` 返回拒绝访问（5）。这属于当前运行权限限制；不能据此断言它是 QEMU 崩溃的唯一原因。
6. 补装官方 API 30 ARM64 镜像并校验归档。模拟器明确拒绝该配置：`arm64` AVD 不支持在此 x86_64 主机上运行；未继续尝试绕开该架构限制。
7. ADB 未发现已启动设备。息屏唤醒、锁屏解除、飞书前台、Doze 和重启测试仍全部未运行。

结论：下载安装已完成，当前障碍是模拟器运行环境及启动故障。下一步需要具有可用虚拟化和必要进程权限的测试环境，或修复当前环境；不应继续把更换 APK 当作解决方法。尚未修改系统驱动、Windows 安全配置或 BIOS。

原报告中“API 30 x86_64 revision 11”指下载归档 `x86_64-30_r11.zip`，其中 `source.properties` 实际标为 revision 10；这项发布元数据差异不改变 API 30 的确认，也不构成开机成功证据。
