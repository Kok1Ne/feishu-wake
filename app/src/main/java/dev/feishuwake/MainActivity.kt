package dev.feishuwake

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.TimePickerDialog
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class MainActivity: Activity() {
    private lateinit var store: Store
    private lateinit var body: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store=Store(this)
        Notices.channels(this)
        // Force-stop removes system alarms; reopening is the user's recovery action.
        if(store.config().enabled) AlarmScheduler.schedule(this)
    }
    override fun onResume() { super.onResume(); render() }

    private fun render() {
        val config=store.config()
        body=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(28,40,28,24) }
        setContentView(ScrollView(this).apply {
            addView(body)
            setOnApplyWindowInsetsListener { view,insets ->
                view.setPadding(insets.systemWindowInsetLeft,insets.systemWindowInsetTop,insets.systemWindowInsetRight,insets.systemWindowInsetBottom)
                insets
            }
        })
        label("Feishu Wake",26f)
        label("按星期和时间唤醒屏幕、解除滑动锁屏并打开飞书。程序不操作打卡。",16f)
        body.addView(Switch(this).apply {
            text="自动化总开关"
            textSize=19f
            isChecked=config.enabled
            setOnCheckedChangeListener { _,enabled ->
                if(enabled) {
                    val issue=config.validate() ?: Notices.problem(this@MainActivity) ?:
                        (if(!AlarmScheduler.exactAllowed(this@MainActivity)) "请先授予精确闹钟权限" else null) ?:
                        (if(packageManager.getLaunchIntentForPackage(store.target())==null) "请先安装飞书" else null)
                    if(issue!=null) { toast(issue); render() }
                    else update(config.copy(enabled=true))
                } else {
                    store.save(config.copy(enabled=false))
                    AlarmScheduler.stop(this@MainActivity)
                    render()
                }
            }
        })
        val due=store.long("nextDue")
        label(if(config.enabled && due>0) "下次执行："+Instant.ofEpochMilli(due).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"))
              else "自动化已关闭")
        label("先完成一次息屏测试并确认飞书进入前台，再打开总开关。安全密码锁屏无法自动解除。",14f)

        label("执行星期",20f)
        val dayNames=listOf("周一","周二","周三","周四","周五","周六","周日")
        for(group in (1..7).chunked(4)) {
            val row=LinearLayout(this).apply { orientation=LinearLayout.HORIZONTAL }
            for(day in group) row.addView(CheckBox(this).apply {
                text=dayNames[day-1]
                isChecked=day in config.days
                setOnCheckedChangeListener { _,checked ->
                    val days=if(checked) config.days+day else config.days-day
                    update(config.copy(days=days))
                }
            },LinearLayout.LayoutParams(0,LinearLayout.LayoutParams.WRAP_CONTENT,1f))
            body.addView(row)
        }

        label("执行时间",20f)
        config.minutes.distinct().sorted().forEach { minute ->
            val row=LinearLayout(this).apply { orientation=LinearLayout.HORIZONTAL }
            row.addView(TextView(this).apply {
                text=String.format(java.util.Locale.ROOT,"%02d:%02d",minute/60,minute%60)
                textSize=22f; setPadding(8,16,8,16)
            },LinearLayout.LayoutParams(0,LinearLayout.LayoutParams.WRAP_CONTENT,1f))
            row.addView(Button(this).apply {
                text="删除"
                contentDescription="删除 "+String.format(java.util.Locale.ROOT,"%02d:%02d",minute/60,minute%60)
                setOnClickListener { update(config.copy(minutes=config.minutes.filter { it!=minute })) }
            })
            body.addView(row)
        }
        button("添加时间") {
            val now=java.time.LocalTime.now()
            TimePickerDialog(this,{ _,hour,minute ->
                val value=hour*60+minute
                if(value in config.minutes) toast("该时间已存在")
                else update(config.copy(minutes=(config.minutes+value).sorted()))
            },now.hour,now.minute,true).show()
        }
        label("修改会取消旧任务并重新计算下次时间；使用手机当前时区。固定定时使用系统可见闹钟，状态栏可能显示下次时间。",13f)
        button("立即测试（15 秒后执行，请息屏）") {
            if(AlarmScheduler.testLater(this)) toast("已安排 15 秒后测试，请按电源键息屏")
            else toast("未成功安排，请查看权限和日志")
        }
        button("取消当前执行（保留定时）") {
            AlarmScheduler.cancel(this,true)
            AlarmScheduler.cancelDirect(this)
            val active=store.active()
            if(active.isNotBlank()) {
                store.log(active,"finish","CANCELLED","用户取消当前执行")
                store.end(active)
                stopService(Intent(this,RunService::class.java))
            }
            Notices.cancel(this)
            render()
        }

        label("权限与运行状态",20f)
        label("精确闹钟："+(if(AlarmScheduler.exactAllowed(this)) "可用" else "未授权")+"\n通知："+(Notices.problem(this) ?: "可用"))
        button("通知与锁屏显示设置") {
            safeSettings(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,packageName))
        }
        if(Build.VERSION.SDK_INT>=33) button("授权通知权限") { requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS),11) }
        if(Build.VERSION.SDK_INT>=31) button("授权精确闹钟") { safeSettings(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,Uri.parse("package:$packageName"))) }
        if(Build.VERSION.SDK_INT>=34) button("授权全屏通知") { safeSettings(Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT,Uri.parse("package:$packageName"))) }
        button("电池优化设置") { safeSettings(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
        button("可选：核实前台状态") {
            AlertDialog.Builder(this).setMessage("默认只记录启动请求。使用情况访问可提供目标前台的辅助证据；程序不保存其他应用名称，不联网。不授权也能执行唤醒。")
                .setNegativeButton("取消",null).setPositiveButton("打开设置") { _,_ ->
                    safeSettings(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS,Uri.parse("package:$packageName")))
                }.show()
        }
        label("手机已亮屏且解锁时，系统可能只显示闹钟横幅；若未自动打开，请点按通知。强制停止后需重新打开本应用恢复任务。realme 的自启动和后台限制需按使用说明配置。",13f)
        if(BuildConfig.DEBUG) {
            button("开发验证：切换飞书 / 测试夹具") {
                store.put("test_target",if(store.string("test_target")=="mock") "" else "mock")
                render()
            }
            button("开发对比 A（已知可能被系统阻止）") { AlarmScheduler.testDirect(this) }
        }

        label("最近执行日志",20f)
        button("刷新日志") { render() }
        button("导出诊断日志") {
            startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                .setType("application/json").putExtra(Intent.EXTRA_TITLE,"FeishuWake-diagnostics.json"),12)
        }
        label(store.logText().ifEmpty { "尚无执行记录" },13f)
    }

    private fun update(config: Config) {
        if(config.enabled && config.validate()!=null) { toast(config.validate()!!); render(); return }
        store.save(config)
        if(!AlarmScheduler.schedule(this)) {
            store.save(config.copy(enabled=false))
            AlarmScheduler.stop(this)
            toast("定时未注册成功，已关闭自动化，请检查权限和日志")
        }
        render()
    }
    private fun label(text: String,size: Float=15f) {
        body.addView(TextView(this).apply { this.text=text; textSize=size; setPadding(0,12,0,12); setTextIsSelectable(true) })
    }
    private fun button(text: String,action: ()->Unit) { body.addView(Button(this).apply { this.text=text; setOnClickListener { action() } }) }
    private fun toast(message: String) { Toast.makeText(this,message,Toast.LENGTH_LONG).show() }
    private fun safeSettings(intent: Intent) { try { startActivity(intent) } catch(_: RuntimeException) { toast("请在系统设置中手动查找此权限") } }
    @Deprecated("Legacy activity result API")
    override fun onActivityResult(requestCode: Int,resultCode: Int,data: Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        if(requestCode==12 && resultCode==RESULT_OK) {
            try {
                val uri=data?.data ?: return
                val output=contentResolver.openOutputStream(uri) ?: throw java.io.IOException("No output stream")
                output.bufferedWriter(Charsets.UTF_8).use { it.write(store.export()) }
                toast("日志已保存")
            } catch(_: Exception) { toast("日志保存失败") }
        }
    }
}
