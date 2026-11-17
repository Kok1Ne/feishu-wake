package dev.feishuwake

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import java.time.Instant
import java.time.ZoneId
import java.util.UUID

object AlarmScheduler {
    private fun alarm(context: Context)=context.getSystemService(AlarmManager::class.java)
    private fun pending(context: Context, manual: Boolean, token: String="", due: Long=0): PendingIntent =
        PendingIntent.getBroadcast(context,if(manual) 200 else 100,
            Intent(context,AlarmReceiver::class.java).setAction(if(manual) "manual" else "scheduled")
                .putExtra("token",token).putExtra("due",due),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    fun exactAllowed(context: Context)=Build.VERSION.SDK_INT<31 || alarm(context).canScheduleExactAlarms()
    fun cancel(context: Context, manual: Boolean) {
        alarm(context).cancel(pending(context,manual))
        val store=Store(context)
        store.put(if(manual) "testToken" else "alarmToken","")
        store.put(if(manual) "testDue" else "nextDue",0L)
    }
    fun schedule(context: Context): Boolean {
        cancel(context,false)
        val store=Store(context)
        val config=store.config()
        if(!config.enabled) return true
        val next=Schedule.next(config,Instant.now(),ZoneId.systemDefault(),store.completed()) ?: return false
        return register(context,false,next.toEpochMilli())
    }
    fun testLater(context: Context): Boolean {
        cancel(context,true)
        cancelDirect(context)
        return register(context,true,System.currentTimeMillis()+15_000)
    }
    fun testDirect(context: Context): Boolean {
        cancel(context,true); cancelDirect(context)
        val store=Store(context)
        if(!exactAllowed(context)) return false
        val token=UUID.randomUUID().toString(); val due=System.currentTimeMillis()+15_000
        store.put("directToken",token); store.put("directDue",due)
        val intent=Intent(context,WakeActivity::class.java).setAction("alarm-direct").putExtra("token",token)
        val pi=PendingIntent.getActivity(context,201,intent,PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return try {
            alarm(context).setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,due,pi)
            store.log("system","schedule","OK","A 路线：15 秒后直接投递 Activity PendingIntent"); true
        } catch(e: RuntimeException) { cancelDirect(context); store.log("system","schedule","FAIL",e.javaClass.simpleName); false }
    }
    fun cancelDirect(context: Context) {
        val pi=PendingIntent.getActivity(context,201,Intent(context,WakeActivity::class.java).setAction("alarm-direct"),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        alarm(context).cancel(pi); Store(context).put("directToken","")
    }
    private fun register(context: Context, manual: Boolean, due: Long): Boolean {
        val store=Store(context)
        if(!exactAllowed(context)) { store.log("system","schedule","FAIL","未授予精确闹钟权限"); return false }
        val token=UUID.randomUUID().toString()
        store.put(if(manual) "testToken" else "alarmToken",token)
        store.put(if(manual) "testDue" else "nextDue",due)
        return try {
            if(manual) {
                alarm(context).setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,due,pending(context,true,token,due))
            } else {
                // Fixed user-selected wake times are visible alarm-clock events.
                // Unlike ordinary allow-while-idle alarms, these are not postponed by standby quotas.
                val show=PendingIntent.getActivity(context,400,Intent(context,MainActivity::class.java),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
                alarm(context).setAlarmClock(AlarmManager.AlarmClockInfo(due,show),pending(context,false,token,due))
            }
            store.log("system","schedule","OK","${if(manual) "息屏测试" else "下次定时"}：${Instant.ofEpochMilli(due).atZone(ZoneId.systemDefault())}")
            true
        } catch(e: RuntimeException) {
            cancel(context,manual); store.log("system","schedule","FAIL",e.javaClass.simpleName); false
        }
    }
    fun stop(context: Context) {
        cancel(context,false); cancel(context,true)
        cancelDirect(context)
        val store=Store(context); val active=store.active()
        if(active.isNotEmpty()) { store.log(active,"finish","CANCELLED","用户关闭自动化"); store.end(active) }
        context.stopService(Intent(context,RunService::class.java))
        Notices.cancel(context)
    }
}
