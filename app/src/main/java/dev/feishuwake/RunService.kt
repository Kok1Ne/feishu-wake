package dev.feishuwake

import android.app.Service
import android.content.Intent
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock

class RunService: Service() {
    private val handler=Handler(Looper.getMainLooper())
    private lateinit var store: Store
    private var id=""
    private var cpu: PowerManager.WakeLock?=null
    private var observed=false
    private var foregroundLogged=false
    private var holding=false
    private var launchedAt=0L
    override fun onCreate() { super.onCreate(); store=Store(this); Notices.channels(this) }
    override fun onBind(intent: Intent?): IBinder?=null
    override fun onStartCommand(intent: Intent?, flags: Int,startId: Int): Int {
        val run=intent?.getStringExtra("run") ?: ""
        if(!store.valid(run)) { stopSelf(); return START_NOT_STICKY }
        if(intent?.action=="hold") {
            if(run==id && !holding) hold()
            return START_NOT_STICKY
        }
        if(id==run) return START_NOT_STICKY
        id=run
        try {
            startForeground(302,Notices.ongoing(this))
            val pm=getSystemService(PowerManager::class.java)
            cpu=pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"FeishuWake:cpu").apply { acquire(150_000) }
            val direct=intent?.getBooleanExtra("direct",false)==true
            val fromActivity=intent?.getBooleanExtra("fromActivity",false)==true
            val issue=Notices.problem(this)
            if(issue!=null && !direct && !fromActivity) { fail("screen",issue); return START_NOT_STICKY }
            if(fromActivity) { /* A route already has a visible Activity. */ }
            else if(direct) startActivity(Notices.wakeIntent(this,id))
            else Notices.manager(this).notify(301,Notices.alarm(this,id))
            handler.postDelayed({
                if(!holding && store.valid(id)) fail("screen","20 秒内唤醒页面未完成；全屏通知可能被限制。亮屏已解锁时系统可能仅显示横幅。")
            },20_000)
        } catch(e: RuntimeException) { fail("screen","唤醒流程异常：${e.javaClass.simpleName}") }
        return START_NOT_STICKY
    }
    private fun hold() {
        holding=true; launchedAt=System.currentTimeMillis()
        Notices.manager(this).cancel(301)
        val seconds=5
        store.log(id,"handoff","OK","已交给目标应用；屏幕熄灭时间遵循系统设置")
        if(!ForegroundEvidence.allowed(this)) {
            store.log(id,"foreground","UNKNOWN","未授权使用情况访问，无法核实飞书前台状态；启动请求不等于前台成功")
            foregroundLogged=true
        }
        val until=SystemClock.elapsedRealtime()+seconds*1000L
        handler.post(object: Runnable {
            override fun run() {
                if(!store.valid(id)) { stopSelf(); return }
                if(!foregroundLogged) {
                    try {
                        observed=ForegroundEvidence.observed(this@RunService,store.target(),launchedAt-2000)
                        if(observed) {
                            store.log(id,"foreground","OBSERVED","使用情况事件中观察到目标应用处于最近恢复状态；不代表打卡成功")
                            foregroundLogged=true
                        }
                    } catch(e: RuntimeException) {
                        store.log(id,"foreground","UNKNOWN",e.javaClass.simpleName); foregroundLogged=true
                    }
                }
                if(SystemClock.elapsedRealtime()>=until) {
                    if(!foregroundLogged) store.log(id,"foreground","UNKNOWN","等待期间未获得可靠的目标前台证据")
                    store.log(id,"finish",if(observed) "OBSERVED" else "REQUESTED","任务结束；不关闭飞书；未验证极速打卡")
                    store.end(id); stopSelf()
                } else handler.postDelayed(this,500)
            }
        })
    }
    private fun fail(stage: String,detail: String) {
        store.log(id,stage,"FAIL",detail)
        store.log(id,"keyguard","SKIPPED","唤醒流程未完成")
        store.log(id,"launch","SKIPPED","唤醒流程未完成")
        store.log(id,"foreground","UNKNOWN","唤醒流程未完成")
        store.log(id,"finish","FAIL","未完成自动启动，详见前序日志")
        Notices.failure(this,detail)
        store.end(id); stopSelf()
    }
    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if(cpu?.isHeld==true) cpu?.release()
        Notices.cancel(this)
        if(id.isNotEmpty() && store.active()==id) { store.log(id,"finish","INTERRUPTED","执行服务停止"); store.end(id) }
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }
}
