package dev.feishuwake

import android.app.KeyguardManager
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import org.json.JSONObject

/** User-controlled Android 11 fallback. No overlay view, screen capture or UI inspection. */
object WakeReadiness {
    fun compatibilityEnabled(c: Context)=Store(c).string("compatWake")=="on"
    fun compatibilityGranted(c: Context)=Build.VERSION.SDK_INT==30 && Settings.canDrawOverlays(c)
    fun compatibilityReady(c: Context)=compatibilityEnabled(c) && compatibilityGranted(c)
    fun problem(c: Context): String? {
        Notices.problem(c)?.let { return it }
        if(!AlarmScheduler.exactAllowed(c)) return "请先授予精确闹钟权限"
        if(c.packageManager.getLaunchIntentForPackage(Store(c).target())==null) return "请先安装飞书"
        if(c.getSystemService(KeyguardManager::class.java).isKeyguardSecure) return "当前为安全锁屏，请先改为非安全的滑动锁屏"
        if(compatibilityEnabled(c) && !compatibilityGranted(c)) return "兼容唤醒尚未获得“显示在其他应用上层”权限"
        return null
    }
    fun snapshot(c: Context): JSONObject {
        val n=c.getSystemService(NotificationManager::class.java)
        val p=c.getSystemService(PowerManager::class.java)
        val k=c.getSystemService(KeyguardManager::class.java)
        val channel=n.getNotificationChannel(Notices.ALARM)
        return JSONObject().put("api",Build.VERSION.SDK_INT)
            .put("interactive",p.isInteractive).put("keyguardLocked",k.isKeyguardLocked)
            .put("keyguardSecure",k.isKeyguardSecure).put("deviceSecure",k.isDeviceSecure)
            .put("notificationsEnabled",n.areNotificationsEnabled())
            .put("alarmChannelImportance",channel?.importance ?: -1)
            .put("alarmChannelSound",channel?.sound?.toString() ?: "")
            .put("alarmChannelVibration",channel?.shouldVibrate() ?: false)
            .put("alarmChannelVisibility",channel?.lockscreenVisibility ?: -1000)
            .put("interruptionFilter",n.currentInterruptionFilter)
            .put("batteryOptimizationExempt",p.isIgnoringBatteryOptimizations(c.packageName))
            .put("powerSaveMode",p.isPowerSaveMode).put("deviceIdle",p.isDeviceIdleMode)
            .put("compatibilityEnabled",compatibilityEnabled(c))
            .put("overlayPermission",Settings.canDrawOverlays(c))
            .put("exactAlarmsAllowed",AlarmScheduler.exactAllowed(c))
    }
    fun record(c: Context,run: String,moment: String) {
        Store(c).log(run,"environment","INFO",snapshot(c).put("moment",moment).toString())
    }
}
