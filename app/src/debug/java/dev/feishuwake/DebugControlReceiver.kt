package dev.feishuwake

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Only packaged in debug; release builds have no externally controlled receiver. */
class DebugControlReceiver: BroadcastReceiver() {
    override fun onReceive(context: Context,intent: Intent) {
        val store=Store(context)
        when(intent.getStringExtra("op")) {
            "fsi_off" -> store.put("suppressFsi","on")
            "fsi_on" -> store.put("suppressFsi","")
            "compat_off" -> store.put("compatWake","")
            "mock" -> store.put("test_target","mock")
            "feishu" -> store.put("test_target","")
            "test_b" -> AlarmScheduler.testLater(context)
            "test_a" -> AlarmScheduler.testDirect(context)
            "configure" -> {
                val config=Config(enabled=intent.getBooleanExtra("enabled",false),
                    days=(intent.getIntArrayExtra("days") ?: intArrayOf(1,2,3,4,5,6,7)).toSet(),
                    minutes=(intent.getIntArrayExtra("minutes") ?: intArrayOf()).toList())
                require(config.validate()==null) { config.validate() ?: "" }
                store.save(config)
                check(AlarmScheduler.schedule(context))
            }
            "enable" -> {
                val config=store.config().copy(enabled=true)
                require(config.validate()==null) { config.validate() ?: "" }
                store.save(config)
                check(AlarmScheduler.schedule(context))
            }
            "stop" -> { store.save(store.config().copy(enabled=false)); AlarmScheduler.stop(context) }
        }
    }
}
