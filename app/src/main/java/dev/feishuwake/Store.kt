package dev.feishuwake

import android.content.Context
import android.os.Build
import android.os.SystemClock
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.UUID

class Store(private val context: Context) {
    private val prefs = context.getSharedPreferences("wake", Context.MODE_PRIVATE)
    fun config(): Config = try {
        val json = JSONObject(prefs.getString("config", "{}") ?: "{}")
        fun ints(name: String, fallback: List<Int>) = json.optJSONArray(name)?.let { a -> (0 until a.length()).map { a.getInt(it) } } ?: fallback
        Config(json.optBoolean("enabled", false), ints("days", (1..5).toList()).toSet(), ints("minutes", listOf(510,1050)).distinct().sorted(), json.optInt("hold",30))
    } catch (_: Exception) { Config() }
    fun save(config: Config) {
        val json=JSONObject().put("enabled",config.enabled).put("days",JSONArray(config.days.sorted())).put("minutes",JSONArray(config.minutes.distinct().sorted())).put("hold",config.holdSeconds)
        check(prefs.edit().putString("config",json.toString()).commit()) { "配置保存失败" }
    }
    fun string(name: String): String = prefs.getString(name, "") ?: ""
    fun long(name: String): Long = prefs.getLong(name, 0)
    fun put(name: String, value: String) { check(prefs.edit().putString(name, value).commit()) }
    fun put(name: String, value: Long) { check(prefs.edit().putLong(name, value).commit()) }
    fun completed(): Set<String> = prefs.getStringSet("completed",emptySet())?.toSet() ?: emptySet()
    fun markCompleted(key: String) {
        val keys = (completed()+key).sorted().takeLast(64).toSet()
        check(prefs.edit().putStringSet("completed",keys).commit())
    }
    fun active(): String = string("active")
    fun begin(source: String): String? {
        if (active().isNotEmpty()) return null
        val id = UUID.randomUUID().toString()
        check(prefs.edit().putString("active",id).putLong("deadline",SystemClock.elapsedRealtime()+150_000).putString("source",source).commit())
        return id
    }
    fun valid(id: String) = id.isNotBlank() && active()==id && SystemClock.elapsedRealtime() < long("deadline")
    fun end(id: String) { if (active()==id) put("active","") }
    fun target(): String = if (BuildConfig.DEBUG && string("test_target")=="mock") "dev.feishuwake.testtarget" else "com.ss.android.lark"
    @Synchronized fun log(run: String, stage: String, status: String, detail: String) {
        val entry=JSONObject().put("at",Instant.now().toString()).put("run",run).put("stage",stage).put("status",status).put("detail",detail)
        val old=try { JSONArray(string("logs")) } catch (_: Exception) { JSONArray() }
        val list=JSONArray()
        for(i in maxOf(0,old.length()-399) until old.length()) list.put(old.get(i))
        list.put(entry)
        check(prefs.edit().putString("logs",list.toString()).commit())
        Log.i("FeishuWake",entry.toString())
    }
    fun logText(): String {
        val array=try { JSONArray(string("logs")) } catch (_: Exception) { JSONArray() }
        return (array.length()-1 downTo 0).joinToString("\n") { i ->
            val e=array.getJSONObject(i)
            "${e.getString("at")} [${e.getString("stage")}] ${e.getString("status")} ${e.getString("detail")}" }
    }
    fun export(): String {
        val keyguard=context.getSystemService(android.app.KeyguardManager::class.java)
        val power=context.getSystemService(android.os.PowerManager::class.java)
        val notices=context.getSystemService(android.app.NotificationManager::class.java)
        return JSONObject().put("appVersion",BuildConfig.VERSION_NAME)
            .put("api",Build.VERSION.SDK_INT).put("manufacturer",Build.MANUFACTURER)
            .put("model",Build.MODEL).put("timezone",java.time.ZoneId.systemDefault().id)
            .put("config",JSONObject(string("config").ifEmpty { "{}" }))
            .put("nextDue",long("nextDue")).put("testDue",long("testDue"))
            .put("activeRun",active()).put("exactAlarmsAllowed",AlarmScheduler.exactAllowed(context))
            .put("notificationsEnabled",notices.areNotificationsEnabled())
            .put("alarmChannelImportance",notices.getNotificationChannel(Notices.ALARM)?.importance ?: -1)
            .put("batteryOptimizationExempt",power.isIgnoringBatteryOptimizations(context.packageName))
            .put("interactive",power.isInteractive).put("keyguardLocked",keyguard.isKeyguardLocked)
            .put("deviceSecure",keyguard.isDeviceSecure)
            .put("userUnlocked",context.getSystemService(android.os.UserManager::class.java).isUserUnlocked)
            .put("foregroundEvidencePermission",ForegroundEvidence.allowed(context))
            .put("targetInstalled",context.packageManager.getLaunchIntentForPackage(target())!=null)
            .put("logs",try { JSONArray(string("logs")) } catch (_: Exception) { JSONArray() }).toString(2)
    }
}
