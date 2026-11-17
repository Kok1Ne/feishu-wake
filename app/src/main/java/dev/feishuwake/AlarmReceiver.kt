package dev.feishuwake

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import java.time.Instant
import java.time.ZoneId

class AlarmReceiver: BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val store=Store(context)
        try {
            val manual=intent.action=="manual"
            if(!manual && intent.action!="scheduled") return
            val token=intent.getStringExtra("token") ?: return
            val due=intent.getLongExtra("due",0)
            if(token.isEmpty() || token!=store.string(if(manual) "testToken" else "alarmToken")) return
            if(!manual && !store.config().enabled) return
            if(due!=store.long(if(manual) "testDue" else "nextDue")) return
            val now=System.currentTimeMillis()
            if(now<due-1000) return
            val key=Schedule.key(Instant.ofEpochMilli(due),ZoneId.systemDefault())
            val duplicate=!manual && key in store.completed()
            if(!manual) store.markCompleted(key)
            if(manual) AlarmScheduler.cancel(context,true) else AlarmScheduler.schedule(context)
            if(duplicate) { store.log(token,"trigger","SKIP","同一时刻已执行"); return }
            if(now-due>15*60_000) { store.log(token,"trigger","FAIL","任务迟到超过 15 分钟，已跳过并安排下次"); return }
            start(context,if(manual) "manual-delay" else "scheduled",false,now-due)
        } catch(e: RuntimeException) { store.log("system","trigger","FAIL",e.javaClass.simpleName) }
    }
    companion object {
        fun start(context: Context, source: String, direct: Boolean, delay: Long=0) {
            val store=Store(context)
            if(store.active().isNotEmpty() && !store.valid(store.active())) store.end(store.active())
            val id=store.begin(source)
            if(id==null) { store.log("system","trigger","SKIP","已有任务执行中"); return }
            store.log(id,"trigger","OK","来源=$source，延迟=${delay}ms")
            try { context.startForegroundService(Intent(context,RunService::class.java).putExtra("run",id).putExtra("direct",direct)) }
            catch(e: RuntimeException) { store.log(id,"finish","FAIL","服务未启动：${e.javaClass.simpleName}"); store.end(id) }
        }
    }
}

class RestoreReceiver: BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val store=Store(context)
        try {
            if(intent.action==Intent.ACTION_BOOT_COMPLETED || intent.action==Intent.ACTION_MY_PACKAGE_REPLACED) {
                store.end(store.active()); AlarmScheduler.cancel(context,true)
            }
            val success=AlarmScheduler.schedule(context)
            store.log("system","restore",if(success) "OK" else "FAIL","${intent.action}；不补执行已过时任务")
        } catch(e: RuntimeException) { store.log("system","restore","FAIL",e.javaClass.simpleName) }
    }
}
