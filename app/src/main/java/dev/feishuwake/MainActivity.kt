package dev.feishuwake

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.TimePickerDialog
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

class MainActivity: Activity() {
    private lateinit var store: Store
    private lateinit var body: LinearLayout
    private lateinit var scroll: ScrollView
    private val handler=Handler(Looper.getMainLooper())
    private var tab=0
    private val expanded=mutableSetOf<String>()
    private val blue=Color.rgb(42,91,221)
    private val ink=Color.rgb(25,42,70)
    private val muted=Color.rgb(101,118,143)
    private val pale=Color.rgb(239,244,255)
    private val canvas=Color.rgb(246,248,252)
    private val line=Color.rgb(226,232,241)
    private val red=Color.rgb(180,49,62)
    private val green=Color.rgb(17,124,92)
    private val dayNames=listOf("周一","周二","周三","周四","周五","周六","周日")
    private val ticker=object: Runnable {
        override fun run() {
            findViewById<TextView>(R.id.test_status)?.text=testStatus()
            handler.postDelayed(this,1000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store=Store(this); tab=savedInstanceState?.getInt("tab") ?: 0
        Notices.channels(this)
        if(Build.VERSION.SDK_INT>=30) window.setDecorFitsSystemWindows(true)
        window.statusBarColor=canvas; window.navigationBarColor=Color.WHITE
        window.decorView.systemUiVisibility=View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        if(store.config().enabled) AlarmScheduler.schedule(this)
    }
    override fun onResume() {
        super.onResume()
        if(store.string("compatPending")=="on") {
            store.put("compatPending","")
            if(WakeReadiness.compatibilityGranted(this)) {
                store.put("compatWake","on")
                store.log("system","settings","OK","用户授权并启用了 Android 11 兼容唤醒")
                toast("兼容唤醒已启用")
            }
        }
        render(); handler.removeCallbacks(ticker); handler.post(ticker)
    }
    override fun onPause() { handler.removeCallbacks(ticker); super.onPause() }
    override fun onSaveInstanceState(out: Bundle) { out.putInt("tab",tab); super.onSaveInstanceState(out) }

    private fun dp(value: Int)=(value*resources.displayMetrics.density+.5f).toInt()
    private fun shape(color: Int,radius: Int=18,border: Int?=null)=GradientDrawable().apply {
        setColor(color); cornerRadius=dp(radius).toFloat()
        if(border!=null) setStroke(dp(1),border)
    }
    private fun column()=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL }
    private fun row()=LinearLayout(this).apply { orientation=LinearLayout.HORIZONTAL; gravity=Gravity.CENTER_VERTICAL }
    private fun space(parent: LinearLayout,size: Int) { parent.addView(View(this),LinearLayout.LayoutParams(1,dp(size))) }
    private fun text(parent: LinearLayout,value: String,size: Float=14f,color: Int=ink,bold: Boolean=false): TextView {
        val view=TextView(this).apply {
            text=value; textSize=size; setTextColor(color); includeFontPadding=false
            if(bold) typeface=Typeface.create("sans-serif-medium",Typeface.NORMAL)
            setLineSpacing(dp(3).toFloat(),1f)
        }
        parent.addView(view,LinearLayout.LayoutParams(-1,-2)); return view
    }
    private fun card(color: Int=Color.WHITE): LinearLayout {
        val panel=column().apply { background=shape(color); setPadding(dp(18),dp(18),dp(18),dp(18)) }
        body.addView(panel,LinearLayout.LayoutParams(-1,-2).apply { bottomMargin=dp(14) })
        return panel
    }
    private fun button(parent: LinearLayout,label: String,primary: Boolean=false,idValue: Int=View.NO_ID,action: ()->Unit): Button {
        val b=Button(this).apply {
            id=idValue; text=label; textSize=15f; isAllCaps=false; minHeight=dp(48)
            minimumHeight=dp(48); minimumWidth=0; stateListAnimator=null
            setPadding(dp(12),dp(10),dp(12),dp(10))
            setTextColor(if(primary) Color.WHITE else blue)
            background=RippleDrawable(ColorStateList.valueOf(Color.argb(35,80,110,180)),
                shape(if(primary) blue else pale,12),null)
            setOnClickListener { action() }
        }
        parent.addView(b,LinearLayout.LayoutParams(-1,-2).apply { topMargin=dp(10) })
        return b
    }
    private fun title(parent: LinearLayout,heading: String,subtitle: String?=null) {
        text(parent,heading,18f,ink,true)
        if(subtitle!=null) { space(parent,7); text(parent,subtitle,13f,muted) }
    }
    private fun render(preserveScroll: Boolean=false) {
        val oldY=if(preserveScroll && ::scroll.isInitialized) scroll.scrollY else 0
        val root=column().apply { setBackgroundColor(canvas); fitsSystemWindows=true }
        val header=column().apply { setPadding(dp(22),dp(17),dp(22),dp(14)) }
        text(header,"Feishu Wake",25f,ink,true)
        space(header,4); text(header,when(tab) {1->"执行记录";2->"权限与唤醒设置";else->"定时唤醒 · Android 11"},12f,muted)
        root.addView(header)
        body=column().apply { setPadding(dp(18),dp(4),dp(18),dp(12)) }
        scroll=ScrollView(this).apply { id=R.id.main_scroll; isFillViewport=true; clipToPadding=false; addView(body) }
        root.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
        when(tab) { 1->renderLogs(); 2->renderSettings(); else->renderSchedule() }
        val nav=row().apply { setBackgroundColor(Color.WHITE); setPadding(dp(14),dp(8),dp(14),dp(8)) }
        listOf("定时","记录","设置").forEachIndexed { index,label ->
            nav.addView(Button(this).apply {
                id=listOf(R.id.navigation_schedule,R.id.navigation_logs,R.id.navigation_settings)[index]
                text=label; textSize=14f; isAllCaps=false; minHeight=dp(48); minimumWidth=0
                setTextColor(if(tab==index) blue else muted)
                background=shape(if(tab==index) pale else Color.WHITE,12); stateListAnimator=null
                setOnClickListener { tab=index; render() }
            },LinearLayout.LayoutParams(0,dp(48),1f).apply { marginStart=dp(3); marginEnd=dp(3) })
        }
        root.addView(nav); setContentView(root)
        if(oldY>0) scroll.post { scroll.scrollTo(0,oldY) }
    }
    private fun renderSchedule() {
        val config=store.config()
        val due=store.long("nextDue")
        val hero=card(blue)
        text(hero,if(config.enabled) "下一次唤醒" else "定时尚未开启",13f,Color.rgb(219,231,255))
        space(hero,10)
        text(hero,if(config.enabled && due>0) time(due,"HH:mm") else "按时唤醒",36f,Color.WHITE,true)
        space(hero,7)
        text(hero,if(config.enabled && due>0) dateLabel(due)+" · 打开飞书" else "先完成息屏测试，再开启长期定时",13f,Color.rgb(224,233,255))
        val toggleCard=card()
        toggleCard.addView(Switch(this).apply {
            id=R.id.automation_toggle; text="自动化总开关"; textSize=16f; setTextColor(ink)
            minHeight=dp(48); isChecked=config.enabled
            setOnCheckedChangeListener { _,enabled ->
                if(enabled) {
                    val issue=store.config().validate() ?: WakeReadiness.problem(this@MainActivity)
                    if(issue!=null) { render(true); showProblem(issue) }
                    else update(store.config().copy(enabled=true))
                } else { store.save(store.config().copy(enabled=false)); AlarmScheduler.stop(this@MainActivity); render(true) }
            }
        },LinearLayout.LayoutParams(-1,-2))
        text(toggleCard,if(config.enabled) "按以下星期和时间持续执行" else "关闭时不会执行后续定时",12f,muted)

        val issue=WakeReadiness.problem(this)
        if(issue!=null) {
            val notice=card(Color.rgb(255,245,237))
            text(notice,"完成设置后再测试",15f,Color.rgb(146,79,31),true)
            space(notice,6); text(notice,issue,13f,ink).id=R.id.readiness_message
            button(notice,"去设置") { openIssue(issue) }
        }
        val trial=card()
        title(trial,"息屏测试","15 秒后执行一次完整流程")
        space(trial,8)
        text(trial,testStatus(),13f,muted).id=R.id.test_status
        button(trial,"立即测试",true,R.id.manual_test) { startTest() }
        if(store.long("testDue")>System.currentTimeMillis() || store.active().isNotEmpty()) {
            button(trial,"取消本次测试") { cancelCurrent() }
        }

        val weekdays=card()
        title(weekdays,"执行星期")
        space(weekdays,12)
        val days=row()
        (1..7).forEach { day ->
            days.addView(Button(this).apply {
                text=listOf("一","二","三","四","五","六","日")[day-1]; textSize=14f
                contentDescription=dayNames[day-1]; isAllCaps=false; minimumWidth=0; minWidth=0
                minimumHeight=dp(44); minHeight=dp(44); setPadding(0,0,0,0); stateListAnimator=null
                val chosen=day in config.days
                setTextColor(if(chosen) Color.WHITE else muted)
                background=shape(if(chosen) blue else canvas,10)
                setOnClickListener {
                    val current=store.config()
                    update(current.copy(days=if(day in current.days) current.days-day else current.days+day))
                }
            },LinearLayout.LayoutParams(0,dp(44),1f).apply { if(day>1) marginStart=dp(4) })
        }
        weekdays.addView(days)
        val times=card()
        title(times,"执行时间","所有时间均应用于已选择的星期")
        if(config.minutes.isEmpty()) { space(times,14); text(times,"还没有时间，添加一个开始。",14f,muted) }
        config.minutes.distinct().sorted().forEach { minute ->
            val item=row().apply { setPadding(0,dp(12),0,dp(6)) }
            val value=minuteText(minute)
            item.addView(TextView(this).apply {
                text=value; textSize=28f; setTextColor(ink); typeface=Typeface.create("sans-serif-medium",Typeface.NORMAL)
                contentDescription="修改 "+value; minHeight=dp(48); gravity=Gravity.CENTER_VERTICAL
                setOnClickListener { editTime(minute) }
            },LinearLayout.LayoutParams(0,-2,1f))
            item.addView(Button(this).apply {
                text="删除"; contentDescription="删除 "+value; textSize=13f; isAllCaps=false
                minimumWidth=0; minWidth=0; minHeight=dp(48); setTextColor(muted)
                background=shape(canvas,12); stateListAnimator=null
                setOnClickListener { val c=store.config(); update(c.copy(minutes=c.minutes.filter { it!=minute })) }
            },LinearLayout.LayoutParams(dp(66),dp(48)))
            times.addView(item)
        }
        button(times,"＋ 添加时间") { editTime(null) }
        space(times,10); text(times,"按手机当前时区执行。修改后会自动取消旧任务。",12f,muted)
        val latest=runs().firstOrNull()
        if(latest!=null) { renderRun(latest.first,latest.second,false); button(body,"查看全部记录") { tab=1; render() } }
    }
    private fun startTest() {
        val issue=WakeReadiness.problem(this)
        if(issue!=null) {
            store.log("system","preflight","BLOCKED",issue)
            showProblem(issue); return
        }
        if(store.active().isNotEmpty() && store.valid(store.active())) { toast("已有任务执行中，请稍候"); return }
        WakeReadiness.record(this,"system","manual_preflight")
        if(AlarmScheduler.testLater(this)) {
            render(true)
            toast("已安排 15 秒后测试，现在请按电源键息屏")
        } else { render(true); showProblem("未成功安排测试，请检查精确闹钟权限") }
    }
    private fun testStatus(): String {
        val remaining=(store.long("testDue")-System.currentTimeMillis()+999)/1000
        return when {
            remaining>0 -> remaining.toString()+" 秒后开始，请按电源键息屏"
            store.active().isNotEmpty() && store.valid(store.active()) -> "正在执行，完成后可在记录中查看"
            WakeReadiness.compatibilityReady(this) -> "兼容唤醒已启用 · 亮屏 → 解锁 → 飞书"
            else -> "点按后按电源键息屏，等待飞书出现在前台"
        }
    }
    private fun editTime(old: Int?) {
        val now=LocalTime.now()
        TimePickerDialog(this,{ _,hour,minute ->
            val value=hour*60+minute; val c=store.config()
            if(value!=old && value in c.minutes) toast("该时间已存在")
            else update(c.copy(minutes=(c.minutes.filter { it!=old }+value).distinct().sorted()))
        },old?.div(60) ?: now.hour,old?.rem(60) ?: now.minute,true).show()
    }
    private fun update(config: Config) {
        if(config.enabled && config.validate()!=null) { toast(config.validate()!!); render(true); return }
        store.save(config)
        if(!AlarmScheduler.schedule(this)) {
            store.save(config.copy(enabled=false)); AlarmScheduler.stop(this)
            toast("定时未注册成功，已关闭自动化，请检查权限")
        }
        render(true)
    }
    private fun cancelCurrent() {
        AlarmScheduler.cancel(this,true); AlarmScheduler.cancelDirect(this)
        val active=store.active()
        if(active.isNotBlank()) { store.log(active,"finish","CANCELLED","用户取消当前执行"); store.end(active); stopService(Intent(this,RunService::class.java)) }
        Notices.cancel(this); render(true)
    }
    private fun renderSettings() {
        val readiness=card()
        title(readiness,"运行检查","测试前先确认这些项目")
        val issue=WakeReadiness.problem(this)
        space(readiness,12)
        text(readiness,issue ?: "基础检查已通过",15f,if(issue==null) green else red,true).id=R.id.readiness_message
        button(readiness,"通知与锁屏显示设置") { openNotifications() }
        text(readiness,"应用通知与“定时唤醒”渠道都需开启，并允许横幅、锁屏显示。",12f,muted)
        if(Build.VERSION.SDK_INT>=33) button(readiness,"授权通知权限") { requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS),11) }
        if(Build.VERSION.SDK_INT>=31) button(readiness,"精确闹钟设置") { safeSettings(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,Uri.parse("package:"+packageName))) }
        if(Build.VERSION.SDK_INT>=34) button(readiness,"全屏通知设置") { safeSettings(Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT,Uri.parse("package:"+packageName))) }

        val compatibility=card()
        title(compatibility,"兼容唤醒","系统未弹出唤醒页面时，可尝试此方式")
        space(compatibility,8)
        compatibility.addView(Switch(this).apply {
            id=R.id.compatibility_toggle; text="启用兼容唤醒"; textSize=15f; setTextColor(ink); minHeight=dp(48)
            isChecked=WakeReadiness.compatibilityEnabled(this@MainActivity)
            isEnabled=Build.VERSION.SDK_INT==30
            setOnCheckedChangeListener { _,on -> changeCompatibility(on) }
        },LinearLayout.LayoutParams(-1,-2))
        text(compatibility,if(Build.VERSION.SDK_INT==30)
            "需要你主动授权“显示在其他应用上层”。仅在任务触发且全屏通知未打开页面时使用；不读取屏幕内容。"
            else "此兼容方式目前仅针对 Android 11 验证。",12f,muted)
        if(WakeReadiness.compatibilityEnabled(this) && !WakeReadiness.compatibilityGranted(this))
            button(compatibility,"完成兼容权限授权") { changeCompatibility(true) }

        val battery=card()
        title(battery,"后台与电池")
        space(battery,10)
        val exempt=getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(packageName)
        text(battery,if(exempt) "电池优化：已豁免" else "电池优化：建议设为不优化",14f,if(exempt) green else muted)
        button(battery,"电池优化设置") { safeSettings(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
        button(battery,"打开应用信息") { safeSettings(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+packageName))) }
        space(battery,6); text(battery,"若系统提供自启动、后台活动或后台弹出界面开关，也需允许本应用正常运行。",12f,muted)

        val optional=card()
        title(optional,"诊断与说明")
        button(optional,"导出诊断日志",false,R.id.export_diagnostics) { exportLogs() }
        button(optional,"可选：核实前台状态") {
            AlertDialog.Builder(this).setTitle("前台状态辅助确认")
                .setMessage("默认只记录启动请求。使用情况访问可辅助判断飞书是否进入前台，不读取页面内容，也不保存其他应用名称。不授权仍可执行唤醒。")
                .setNegativeButton("取消",null).setPositiveButton("打开设置") { _,_ ->
                    safeSettings(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS,Uri.parse("package:"+packageName)))
                }.show()
        }
        button(optional,"取消当前执行（保留定时）") { cancelCurrent() }
        space(optional,10)
        text(optional,"仅解除非安全滑动锁屏，不操作考勤。强行停止后需重新打开本应用恢复任务。",12f,muted)
        space(optional,7); text(optional,"版本 "+BuildConfig.VERSION_NAME+" · Android 11",12f,muted)
        if(BuildConfig.DEBUG) {
            button(optional,"开发验证：切换飞书 / 测试夹具") { store.put("test_target",if(store.string("test_target")=="mock") "" else "mock"); render(true) }
            button(optional,"开发对比 A") { AlarmScheduler.testDirect(this) }
        }
    }
    private fun changeCompatibility(on: Boolean) {
        if(!on) { store.put("compatWake",""); render(true); return }
        render(true)
        val granted=WakeReadiness.compatibilityGranted(this)
        AlertDialog.Builder(this).setTitle("启用兼容唤醒")
            .setMessage("当系统未打开全屏通知时，借助 Android 11 的“显示在其他应用上层”权限尝试打开唤醒页面。\n\n本应用不绘制悬浮广告、不读取或截取屏幕、不点击其他应用。权限只用于你设置的定时或手动测试，默认关闭，可随时取消。")
            .setNegativeButton("暂不启用",null)
            .setPositiveButton(if(granted) "启用" else "前往授权") { _,_ ->
                if(granted) {
                    store.put("compatWake","on"); store.log("system","settings","OK","用户主动启用兼容唤醒"); render(true)
                } else {
                    store.put("compatPending","on")
                    safeSettings(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,Uri.parse("package:"+packageName)))
                }
            }.show()
    }
    private fun renderLogs() {
        val intro=card()
        title(intro,"最近执行","按一次任务展示结果，点开可查看具体步骤")
        button(intro,"刷新记录") { render(true) }
        button(intro,"导出诊断日志",false,R.id.export_diagnostics) { exportLogs() }
        val entries=runs()
        if(entries.isEmpty()) {
            val empty=card(); space(empty,18); text(empty,"还没有执行记录",18f,ink,true)
            space(empty,10); text(empty,"完成一次息屏测试后，会在这里显示结果。",14f,muted); space(empty,18)
        } else entries.take(8).forEach { renderRun(it.first,it.second,true) }
        val system=store.events().filter { it.optString("run")=="system" && it.optString("stage")!="environment" }.takeLast(3)
        if(system.isNotEmpty()) {
            val panel=card(); title(panel,"最近调度与设置")
            system.asReversed().forEach { e ->
                space(panel,12); text(panel,eventTime(e)+"  "+stageName(e.optString("stage")),12f,muted)
                space(panel,4); text(panel,e.optString("detail"),13f,ink)
            }
        }
    }
    private fun runs(): List<Pair<String,List<JSONObject>>> = store.events()
        .filter { it.optString("run").isNotEmpty() && it.optString("run")!="system" }
        .groupBy { it.optString("run") }.entries.toList().asReversed().map { it.key to it.value }

    private fun renderRun(id: String,rows: List<JSONObject>,expandable: Boolean) {
        val panel=card()
        val failure=rows.firstOrNull { it.optString("status")=="FAIL" && it.optString("stage")!="finish" }
        val end=rows.lastOrNull { it.optString("stage")=="finish" }
        val state=when {
            failure!=null -> "本次未完成"
            end?.optString("status")=="OBSERVED" -> "已观察到飞书前台"
            end?.optString("status")=="REQUESTED" -> "启动请求已发送"
            end?.optString("status")=="CANCELLED" -> "本次已取消"
            end?.optString("status")=="INTERRUPTED" -> "执行被中断"
            else -> "正在执行"
        }
        text(panel,state,16f,if(failure!=null) red else if(end?.optString("status") in listOf("OBSERVED","REQUESTED")) green else ink,true)
        space(panel,6)
        val kind=if(rows.any { it.optString("detail").contains("scheduled") }) "定时任务" else "手动测试"
        text(panel,eventTime(rows.first(),true)+" · "+kind,12f,muted)
        space(panel,10)
        text(panel,failure?.optString("detail") ?: when(end?.optString("status")) {
            "REQUESTED" -> "系统已接受启动请求，前台与考勤结果需另行确认。"
            "OBSERVED" -> "已获得目标应用前台事件，不代表考勤成功。"
            "CANCELLED" -> "任务已按你的操作取消。"
            else -> "等待本次流程结束后刷新查看。"
        },13f,ink)
        if(failure!=null && failure.optString("stage")=="screen")
            button(panel,"检查唤醒设置") { tab=2; render() }
        if(expandable) {
            button(panel,if(id in expanded) "收起步骤" else "查看步骤") {
                if(!expanded.add(id)) expanded.remove(id); render(true)
            }
            if(id in expanded) rows.filter { it.optString("stage")!="environment" }.forEach { e ->
                space(panel,12)
                val status=e.optString("status")
                text(panel,eventTime(e)+"  "+stageName(e.optString("stage")),12f,muted)
                space(panel,4); text(panel,e.optString("detail"),13f,if(status=="FAIL") red else ink)
            }
        }
    }
    private fun stageName(stage: String)=mapOf(
        "trigger" to "任务触发","notification" to "唤醒通知","screen" to "点亮屏幕",
        "activity_created" to "唤醒页面","activity_resumed" to "页面可见","activity_timeout" to "页面超时",
        "keyguard" to "解除锁屏","keyguard_state" to "锁屏状态","keyguard_request" to "请求解锁",
        "launch" to "打开飞书","foreground" to "前台状态","finish" to "任务结束",
        "handoff" to "应用交接","compatibility" to "兼容唤醒","schedule" to "定时安排",
        "restore" to "任务恢复","settings" to "设置变更","preflight" to "测试前检查"
    )[stage] ?: "运行记录"
    private fun eventTime(e: JSONObject,date: Boolean=false)=try {
        time(Instant.parse(e.getString("at")).toEpochMilli(),if(date) "MM-dd HH:mm:ss" else "HH:mm:ss")
    } catch(_: Exception) { "" }
    private fun time(millis: Long,pattern: String)=Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern(pattern,Locale.CHINA))
    private fun dateLabel(millis: Long): String {
        val date=Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault())
        val day=when(date.toLocalDate()) { LocalDate.now()->"今天"; LocalDate.now().plusDays(1)->"明天"; else->date.format(DateTimeFormatter.ofPattern("M月d日")) }
        return day+" · "+dayNames[date.dayOfWeek.value-1]
    }
    private fun minuteText(value: Int)=String.format(Locale.ROOT,"%02d:%02d",value/60,value%60)
    private fun openNotifications() {
        val intent=if(Notices.manager(this).areNotificationsEnabled())
            Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,packageName).putExtra(Settings.EXTRA_CHANNEL_ID,Notices.ALARM)
        else Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,packageName)
        safeSettings(intent)
    }
    private fun showProblem(issue: String) {
        AlertDialog.Builder(this).setTitle("先完成设置").setMessage(issue)
            .setNegativeButton("知道了",null).setPositiveButton("去设置") { _,_ -> openIssue(issue) }.show()
    }
    private fun openIssue(issue: String) {
        when {
            issue.contains("通知") -> openNotifications()
            issue.contains("兼容") -> { tab=2; render(); changeCompatibility(true) }
            issue.contains("锁屏") -> safeSettings(Intent(Settings.ACTION_SECURITY_SETTINGS))
            issue.contains("精确闹钟") && Build.VERSION.SDK_INT>=31 -> safeSettings(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,Uri.parse("package:"+packageName)))
            else -> { tab=2; render() }
        }
    }
    private fun exportLogs() {
        startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType("application/json").putExtra(Intent.EXTRA_TITLE,"FeishuWake-diagnostics.json"),12)
    }
    private fun toast(message: String) { Toast.makeText(this,message,Toast.LENGTH_LONG).show() }
    private fun safeSettings(intent: Intent) { try { startActivity(intent) } catch(_: RuntimeException) { toast("请在系统设置中查找此项") } }
    @Deprecated("Legacy activity result API")
    override fun onActivityResult(requestCode: Int,resultCode: Int,data: Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        if(requestCode==12 && resultCode==RESULT_OK) {
            try {
                val uri=data?.data ?: return
                val output=contentResolver.openOutputStream(uri) ?: throw java.io.IOException("No output stream")
                output.bufferedWriter(Charsets.UTF_8).use { it.write(store.export()) }; toast("日志已保存")
            } catch(_: Exception) { toast("日志保存失败") }
        }
    }
}
