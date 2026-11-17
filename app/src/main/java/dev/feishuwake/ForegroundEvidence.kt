package dev.feishuwake

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.os.Process

object ForegroundEvidence {
    fun allowed(c: Context): Boolean = c.getSystemService(AppOpsManager::class.java)
        .checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS,Process.myUid(),c.packageName)==AppOpsManager.MODE_ALLOWED
    fun observed(c: Context,target: String,since: Long): Boolean {
        if(!allowed(c)) return false
        val events=c.getSystemService(UsageStatsManager::class.java).queryEvents(since,System.currentTimeMillis()) ?: return false
        var lastResumed: String?=null
        val event=UsageEvents.Event()
        while(events.hasNextEvent()) {
            events.getNextEvent(event)
            // MOVE_TO_FOREGROUND and ACTIVITY_RESUMED both use event value 1.
            if(event.eventType==UsageEvents.Event.MOVE_TO_FOREGROUND) lastResumed=event.packageName
            if(event.eventType==UsageEvents.Event.MOVE_TO_BACKGROUND && lastResumed==event.packageName) lastResumed=null
        }
        return lastResumed==target
    }
}
