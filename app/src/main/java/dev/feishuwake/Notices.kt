package dev.feishuwake

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build

object Notices {
    const val ALARM="wake_alarm_v1"
    const val SERVICE="wake_service_v1"
    fun manager(c: Context)=c.getSystemService(NotificationManager::class.java)
    fun channels(c: Context) {
        manager(c).createNotificationChannel(NotificationChannel(ALARM,"定时唤醒（允许锁屏弹出）",NotificationManager.IMPORTANCE_HIGH).apply {
            description="仅在您设置的时间触发，可关闭总开关停止"; lockscreenVisibility=Notification.VISIBILITY_PUBLIC
            setSound(null,null); enableVibration(false)
        })
        manager(c).createNotificationChannel(NotificationChannel(SERVICE,"任务执行状态",NotificationManager.IMPORTANCE_LOW))
    }
    fun problem(c: Context): String? {
        channels(c)
        if(Build.VERSION.SDK_INT>=33 && c.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) return "未授权通知权限"
        if(!manager(c).areNotificationsEnabled()) return "通知已关闭"
        if(manager(c).getNotificationChannel(ALARM).importance<NotificationManager.IMPORTANCE_HIGH) return "定时唤醒通知需要设为高优先级并允许横幅/锁屏显示"
        if(Build.VERSION.SDK_INT>=34 && !manager(c).canUseFullScreenIntent()) return "未授权全屏通知"
        return null
    }
    fun wakeIntent(c: Context,id: String)=Intent(c,WakeActivity::class.java).putExtra("run",id).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
    fun alarm(c: Context,id: String): Notification {
        val pi=PendingIntent.getActivity(c,301,wakeIntent(c,id),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val builder=Notification.Builder(c,ALARM).setSmallIcon(R.drawable.ic_wake).setContentTitle("Feishu Wake 定时唤醒")
            .setContentText("正在尝试点亮屏幕并打开飞书；点按可继续")
            .setCategory(Notification.CATEGORY_ALARM).setVisibility(Notification.VISIBILITY_PUBLIC)
            .setContentIntent(pi).setAutoCancel(true).setTimeoutAfter(25_000)
        // Debug-only fault injection exercises a blocked full-screen delivery on the cloud emulator.
        if(!(BuildConfig.DEBUG && Store(c).string("suppressFsi")=="on")) builder.setFullScreenIntent(pi,true)
        return builder.build()
    }
    fun ongoing(c: Context): Notification {
        val pi=PendingIntent.getActivity(c,302,Intent(c,MainActivity::class.java),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(c,SERVICE).setSmallIcon(R.drawable.ic_wake).setContentTitle("Feishu Wake 任务执行中")
            .setContentText("完成后自动释放亮屏保持；点按查看日志")
            .setContentIntent(pi).setOngoing(true).build()
    }
    fun cancel(c: Context) { manager(c).cancel(301); manager(c).cancel(302) }
    fun failure(c: Context,detail: String) {
        if(!manager(c).areNotificationsEnabled()) return
        val pi=PendingIntent.getActivity(c,303,Intent(c,MainActivity::class.java),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        manager(c).notify(303,Notification.Builder(c,SERVICE).setSmallIcon(R.drawable.ic_wake)
            .setContentTitle("Feishu Wake 本次任务未完成").setContentText(detail).setContentIntent(pi).setAutoCancel(true).build())
    }
}
