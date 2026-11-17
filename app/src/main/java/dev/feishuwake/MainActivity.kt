package dev.feishuwake

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/** Deliberately minimal P0/P1 interface; scheduling UI is gated on runtime validation. */
class MainActivity: Activity() {
    private lateinit var store: Store
    private lateinit var body: LinearLayout
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState); store=Store(this); Notices.channels(this)
    }
    override fun onResume() { super.onResume(); render() }
    private fun render() {
        body=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(28,40,28,24) }
        setContentView(ScrollView(this).apply { addView(body); setOnApplyWindowInsetsListener { v,i -> v.setPadding(i.systemWindowInsetLeft,i.systemWindowInsetTop,i.systemWindowInsetRight,i.systemWindowInsetBottom); i } })
        label("Feishu Wake · 核心验证",26f)
        label("先验证息屏 → 亮屏 → 解除滑动锁屏 → 打开飞书。程序不执行打卡操作。",16f)
        label("目标：${store.target()}\n系统：Android ${Build.VERSION.RELEASE}\n精确闹钟：${if(AlarmScheduler.exactAllowed(this)) "可用" else "未授权"}\n通知：${Notices.problem(this) ?: "可用"}")
        button("立即测试（当前亮屏）") { AlarmReceiver.start(this,"manual-now",true) }
        button("15 秒后测试 B：全屏通知") { result(AlarmScheduler.testLater(this)) }
        button("15 秒后测试 A：直接启动") { result(AlarmScheduler.testDirect(this)) }
        button("取消测试 / 停止执行") { store.save(store.config().copy(enabled=false)); AlarmScheduler.stop(this); render() }
        button("通知与锁屏显示设置") { safeSettings(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,packageName)) }
        if(Build.VERSION.SDK_INT>=33) button("授权通知权限") { requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS),11) }
        if(Build.VERSION.SDK_INT>=31) button("授权精确闹钟") { safeSettings(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,Uri.parse("package:$packageName"))) }
        if(Build.VERSION.SDK_INT>=34) button("授权全屏通知") { safeSettings(Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT,Uri.parse("package:$packageName"))) }
        button("可选：前台状态核实权限") {
            AlertDialog.Builder(this).setMessage("默认仅记录启动请求。使用情况访问可提供目标前台的辅助证据；程序不保存其他应用名称，不联网。是否打开系统授权页面？")
                .setNegativeButton("取消",null).setPositiveButton("打开设置") { _,_ -> safeSettings(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS,Uri.parse("package:$packageName"))) }.show()
        }
        button("电池优化设置") { safeSettings(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
        button("刷新日志") { render() }
        button("导出诊断日志") { startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json").putExtra(Intent.EXTRA_TITLE,"FeishuWake-diagnostics.json"),12) }
        if(BuildConfig.DEBUG) button("开发验证：切换飞书 / 测试目标") {
            store.put("test_target",if(store.string("test_target")=="mock") "" else "mock"); render()
        }
        label("最近执行日志",20f)
        label(store.logText().ifEmpty { "尚无执行记录" },13f)
    }
    private fun label(text: String,size: Float=15f) { body.addView(TextView(this).apply { this.text=text; textSize=size; setPadding(0,12,0,12); setTextIsSelectable(true) }) }
    private fun button(text: String,action: ()->Unit) { body.addView(Button(this).apply { this.text=text; setOnClickListener { action() } }) }
    private fun result(ok: Boolean) { Toast.makeText(this,if(ok) "已安排 15 秒后测试，请按电源键息屏" else "未成功安排，请查看权限和日志",Toast.LENGTH_LONG).show() }
    private fun safeSettings(intent: Intent) { try { startActivity(intent) } catch(_: RuntimeException) { Toast.makeText(this,"请在系统设置中手动查找此权限",Toast.LENGTH_LONG).show() } }
    @Deprecated("Legacy activity result API is sufficient for this small app")
    override fun onActivityResult(requestCode: Int,resultCode: Int,data: Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        if(requestCode==12 && resultCode==RESULT_OK) {
            try { data?.data?.let { uri -> contentResolver.openOutputStream(uri)?.bufferedWriter(Charsets.UTF_8)?.use { it.write(store.export()) } } }
            catch(_: Exception) { Toast.makeText(this,"日志保存失败",Toast.LENGTH_LONG).show() }
        }
    }
}
