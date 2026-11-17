package dev.feishuwake

import android.app.KeyguardManager
import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Until
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CoreInstrumentedTest {
    @Test fun configRoundTripAndCancellation() {
        val c=InstrumentationRegistry.getInstrumentation().targetContext
        val store=Store(c)
        val config=Config(enabled=true,days=setOf(2,4),minutes=listOf(120,700))
        store.save(config); assertEquals(config,store.config())
        assertTrue(AlarmScheduler.schedule(c)); assertTrue(store.long("nextDue")>System.currentTimeMillis())
        store.save(config.copy(enabled=false)); AlarmScheduler.stop(c)
        assertEquals(0L,store.long("nextDue")); assertEquals("",store.string("alarmToken"))
    }
    @Test fun screenOffFullScreenFlowToFixture() {
        val i=InstrumentationRegistry.getInstrumentation(); val c=i.targetContext
        val store=Store(c); val device=UiDevice.getInstance(i)
        assertFalse("This test requires a swipe-only lock screen",c.getSystemService(KeyguardManager::class.java).isKeyguardSecure)
        assertNotNull("Install the separate test fixture first",c.packageManager.getLaunchIntentForPackage("dev.feishuwake.testtarget"))
        store.put("test_target","mock")
        i.runOnMainSync { assertTrue(AlarmScheduler.testLater(c)) }
        device.pressHome(); device.sleep()
        assertFalse(device.isScreenOn)
        assertTrue("Expected test target in foreground after wake and unlock",device.wait(Until.hasObject(By.pkg("dev.feishuwake.testtarget").depth(0)),40_000))
        assertTrue(device.isScreenOn)
        assertFalse(c.getSystemService(KeyguardManager::class.java).isKeyguardLocked)
        // This fixture test is expressly NOT evidence that real Feishu was tested.
    }
}
