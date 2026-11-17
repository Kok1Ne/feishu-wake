package dev.feishuwake

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Only packaged in debug; never permits external control of a release install. */
class DebugControlReceiver: BroadcastReceiver() {
    override fun onReceive(context: Context,intent: Intent) {
        val store=Store(context)
        when(intent.getStringExtra("op")) {
            "mock" -> store.put("test_target","mock")
            "feishu" -> store.put("test_target","")
            "test_b" -> AlarmScheduler.testLater(context)
            "test_a" -> AlarmScheduler.testDirect(context)
            "stop" -> { store.save(store.config().copy(enabled=false)); AlarmScheduler.stop(context) }
        }
    }
}
