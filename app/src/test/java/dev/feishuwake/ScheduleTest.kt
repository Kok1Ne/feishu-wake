package dev.feishuwake

import org.junit.Assert.*
import org.junit.Test
import java.time.Instant
import java.time.ZoneId

class ScheduleTest {
    private val zone=ZoneId.of("Asia/Shanghai")
    private val config=Config(enabled=true)
    @Test fun weekdayMorning() { assertEquals(Instant.parse("2026-11-17T00:30:00Z"),Schedule.next(config,Instant.parse("2026-11-17T00:00:00Z"),zone)) }
    @Test fun exactTimeIsNotRepeated() { assertEquals(Instant.parse("2026-11-17T09:30:00Z"),Schedule.next(config,Instant.parse("2026-11-17T00:30:00Z"),zone)) }
    @Test fun fridayEveningRollsToMonday() { assertEquals(Instant.parse("2026-11-23T00:30:00Z"),Schedule.next(config,Instant.parse("2026-11-20T10:00:00Z"),zone)) }
    @Test fun disablingHasNoNextAlarm() { assertNull(Schedule.next(config.copy(enabled=false),Instant.now(),zone)) }
    @Test fun emptyDaysRejected() { assertNotNull(config.copy(days=emptySet()).validate()) }
    @Test fun invalidMinuteRejected() { assertNotNull(config.copy(minutes=listOf(1440)).validate()) }
    @Test fun unorderedDuplicateTimes() { assertEquals(Instant.parse("2026-11-17T00:30:00Z"),Schedule.next(config.copy(minutes=listOf(1050,510,510)),Instant.parse("2026-11-17T00:00:00Z"),zone)) }
    @Test fun completedMinuteSkipped() { assertEquals(Instant.parse("2026-11-17T09:30:00Z"),Schedule.next(config,Instant.parse("2026-11-17T00:00:00Z"),zone,setOf("2026-11-17T08:30"))) }
    @Test fun sundayOnly() { assertEquals(Instant.parse("2026-11-22T00:30:00Z"),Schedule.next(config.copy(days=setOf(7)),Instant.parse("2026-11-17T00:00:00Z"),zone)) }
    @Test fun springDstGap() { assertEquals(Instant.parse("2026-03-08T07:30:00Z"),Schedule.next(config.copy(days=(1..7).toSet(),minutes=listOf(150)),Instant.parse("2026-03-08T06:00:00Z"),ZoneId.of("America/New_York"))) }
    @Test fun autumnDstNeverFiresTwice() { assertEquals(Instant.parse("2026-11-02T06:30:00Z"),Schedule.next(config.copy(days=(1..7).toSet(),minutes=listOf(90)),Instant.parse("2026-11-01T05:30:00Z"),ZoneId.of("America/New_York"))) }
}
