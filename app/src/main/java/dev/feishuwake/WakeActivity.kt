package dev.feishuwake

import android.app.Activity
import android.app.KeyguardManager
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.view.WindowManager
import android.widget.TextView

class WakeActivity: Activity() {
    private val handler=Handler(Looper.getMainLooper())
    private lateinit var store: Store
    private var id=""
    private var started=false
    private var launched=false
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState); store=Store(this)
        if(intent.action=="alarm-direct") {
            val token=intent.getStringExtra("token") ?: ""
            val due=store.long("directDue")
            if(token.isEmpty() || token!=store.string("directToken") || System.currentTimeMillis()<due-1000 || System.currentTimeMillis()-due>60_000) { finish(); return }
            store.put("directToken","")
            id=store.begin("manual-direct") ?: run { finish(); return }
            store.log(id,"trigger","OK","A 路线 Activity 已收到定时投递；延迟=${System.currentTimeMillis()-due}ms")
            try { startForegroundService(Intent(this,RunService::class.java).putExtra("run",id).putExtra("fromActivity",true)) }
            catch(e: RuntimeException) { store.log(id,"finish","FAIL",e.javaClass.simpleName); store.end(id); finish(); return }
        } else {
        id=intent.getStringExtra("run") ?: ""
        }
        if(!store.valid(id)) { finish(); return }
        store.put("wakeCreatedRun",id)
        store.log(id,"activity_created","OK","系统已创建唤醒页面")
        WakeReadiness.record(this,id,"activity_created")
        setShowWhenLocked(true); setTurnScreenOn(true)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(android.widget.LinearLayout(this).apply {
            orientation=android.widget.LinearLayout.VERTICAL
            gravity=android.view.Gravity.CENTER
            setBackgroundColor(android.graphics.Color.rgb(244,247,253))
            setPadding(32,32,32,32)
            addView(TextView(this@WakeActivity).apply {
                text="Feishu Wake"; textSize=26f; setTextColor(android.graphics.Color.rgb(28,43,70))
                gravity=android.view.Gravity.CENTER
            })
            addView(TextView(this@WakeActivity).apply {
                text="正在唤醒，请稍候"; textSize=16f; setPadding(0,24,0,0)
                setTextColor(android.graphics.Color.rgb(85,103,131)); gravity=android.view.Gravity.CENTER
            })
        })
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handler.removeCallbacksAndMessages(null)
        id=intent.getStringExtra("run") ?: ""
        started=false; launched=false
        if(!store.valid(id)) { finish(); return }
        store.put("wakeCreatedRun",id)
        setShowWhenLocked(true); setTurnScreenOn(true)
        store.log(id,"activity_created","OK","现有唤醒页面收到新的任务")
        if(hasWindowFocus()) beginWake()
    }
    override fun onResume() {
        super.onResume()
        if(!::store.isInitialized) return
        if(!store.valid(id)) { finish(); return }
        store.put("wakeResumedRun",id)
        store.log(id,"activity_resumed","OK","唤醒页面已进入前台生命周期")
        WakeReadiness.record(this,id,"activity_resumed")
        beginWake()
    }
    private fun beginWake() {
        if(started || !store.valid(id)) return
        started=true
        handler.postDelayed({ checkScreen(0) },100)
    }
    private fun checkScreen(attempt: Int) {
        if(!store.valid(id)) { finish(); return }
        if(getSystemService(PowerManager::class.java).isInteractive) {
            store.log(id,"screen","OK","系统报告屏幕处于交互状态")
            dismiss()
        } else if(attempt<20) handler.postDelayed({checkScreen(attempt+1)},100)
        else fail("screen","屏幕未进入交互状态")
    }
    private fun dismiss() {
        val keyguard=getSystemService(KeyguardManager::class.java)
        store.log(id,"keyguard_state","INFO","isDeviceSecure=${keyguard.isDeviceSecure}; isKeyguardSecure=${keyguard.isKeyguardSecure}; isKeyguardLocked=${keyguard.isKeyguardLocked}")
        if(!keyguard.isKeyguardLocked) { store.log(id,"keyguard","OK","当前没有锁屏"); launch(); return }
        if(keyguard.isKeyguardSecure) { fail("keyguard","检测到安全锁屏；请自行解锁，不尝试绕过认证"); return }
        store.log(id,"keyguard_request","REQUESTED","已请求系统解除非安全锁屏")
        val requestedRun=id
        handler.postDelayed({ if(!launched) { if(store.valid(id)) fail("keyguard","解除锁屏请求超时") else finish() } },8000)
        try {
            keyguard.requestDismissKeyguard(this,object: KeyguardManager.KeyguardDismissCallback() {
                override fun onDismissSucceeded() {
                    if(id!=requestedRun || !store.valid(id)) return
                    if(keyguard.isKeyguardLocked) { fail("keyguard","系统回调成功但锁屏仍存在"); return }
                    store.log(id,"keyguard","OK","系统确认已解除非安全锁屏"); launch()
                }
                override fun onDismissCancelled() { if(id==requestedRun) fail("keyguard","系统取消了解锁请求") }
                override fun onDismissError() { if(id==requestedRun) fail("keyguard","系统拒绝解除锁屏") }
            })
        } catch(e: RuntimeException) { fail("keyguard",e.javaClass.simpleName) }
    }
    private fun launch() {
        if(launched || !store.valid(id)) return
        launched=true
        try {
            val target=store.target()
            val launch=packageManager.getLaunchIntentForPackage(target)
            if(launch==null) { fail("launch","未找到已安装的飞书或可启动页面"); return }
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)
            // The stock launcher intent brings the existing task forward, without clearing it.
            startActivity(launch)
            store.log(id,"launch","REQUESTED","系统已接受启动请求；尚不能据此确认前台状态")
            startService(Intent(this,RunService::class.java).setAction("hold").putExtra("run",id))
            finish()
        } catch(e: RuntimeException) { fail("launch",e.javaClass.simpleName) }
    }
    private fun fail(stage: String,detail: String) {
        if(!store.valid(id)) { finish(); return }
        store.log(id,stage,"FAIL",detail)
        store.log(id,"foreground","UNKNOWN","目标启动流程未完成")
        store.log(id,"finish","FAIL","停止当前任务，保留后续定时配置")
        Notices.failure(this,detail)
        store.end(id); stopService(Intent(this,RunService::class.java)); finish()
    }
    override fun onDestroy() { handler.removeCallbacksAndMessages(null); super.onDestroy() }
}
