package dev.feishuwake

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZonedDateTime

data class Config(
    val enabled: Boolean = false,
    val days: Set<Int> = (1..5).toSet(),
    val minutes: List<Int> = listOf(8 * 60 + 30, 17 * 60 + 30),
    val holdSeconds: Int = 30
) {
    fun validate(): String? = when {
        days.isEmpty() -> "请至少选择一个执行星期"
        days.any { it !in 1..7 } -> "星期配置无效"
        minutes.isEmpty() -> "请至少添加一个执行时间"
        minutes.any { it !in 0..1439 } -> "执行时间无效"
        holdSeconds !in 5..120 -> "亮屏保持时间需要在 5–120 秒之间"
        else -> null
    }
}

object Schedule {
    fun key(time: Instant, zone: ZoneId): String = time.atZone(zone).toLocalDateTime().withSecond(0).withNano(0).toString()
    fun next(config: Config, after: Instant, zone: ZoneId, completed: Set<String> = emptySet()): Instant? {
        if (!config.enabled || config.validate() != null) return null
        val date = after.atZone(zone).toLocalDate()
        val candidates = mutableListOf<Instant>()
        for (offset in 0L..8L) {
            val day: LocalDate = date.plusDays(offset)
            if (day.dayOfWeek.value !in config.days) continue
            for (m in config.minutes.distinct()) {
                // ZonedDateTime shifts nonexistent local times forward through a DST gap.
                // During a repeated hour, use only the earlier offset; one firing per local minute.
                val candidate = ZonedDateTime.of(day, java.time.LocalTime.of(m / 60, m % 60), zone).toInstant()
                if (candidate > after && key(candidate, zone) !in completed) candidates += candidate
            }
        }
        return candidates.minOrNull()
    }
}
