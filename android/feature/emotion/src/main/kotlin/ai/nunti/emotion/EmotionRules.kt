package ai.nunti.emotion

import java.util.Properties

/**
 * 감정 전환 규칙의 수치. 값은 emotion.properties 에서 읽는다 (모두 ms, 신뢰도는 0..1).
 * 이 값이 바뀌면 저장된 이벤트 기록을 같은 결과로 재생할 수 없으므로 기록의 ruleDigest 가 달라진다.
 *
 * - confidenceMin: 이 신뢰도 미만의 이벤트는 무시
 * - eventExpiry: 이벤트가 발생한 지 이만큼 지나면 무시 (대기 중인 전환도 폐기)
 * - debounce: 같은 종류 이벤트의 최소 간격
 * - cooldown: 같은 부정 감정(걱정·놀람)이 다시 나타나기까지의 최소 간격
 * - minimumDwell: 한 감정을 최소한 유지하는 시간
 * - stableWindow / stableGap: 안정 주행이 이만큼 이어지고(window), 이벤트 사이가 이 간격(gap) 이하여야 안도로 간다
 * - startledMax / concernedMax: 놀람·걱정이 회복 없이 중립으로 돌아가는 시간
 * - reliefDwell: 안도가 편안으로 정착하는 시간
 * - dataExpiry: 마지막으로 확인된 이벤트 이후 이만큼 지나면 중립으로 돌아간다
 */
data class EmotionRules(val confidenceMin: Double, val eventExpiry: Long, val debounce: Long, val cooldown: Long,
    val minimumDwell: Long, val stableWindow: Long, val stableGap: Long, val startledMax: Long,
    val concernedMax: Long, val reliefDwell: Long, val dataExpiry: Long) {
    init {
        require(confidenceMin.isFinite() && confidenceMin in 0.0..1.0)
        require(listOf(eventExpiry, debounce, cooldown, minimumDwell, stableWindow, stableGap,
            startledMax, concernedMax, reliefDwell, dataExpiry).all { it > 0 && it <= 3_600_000 })
        require(startledMax >= minimumDwell && concernedMax >= minimumDwell && reliefDwell >= minimumDwell)
    }
    companion object {
        fun from(p: Properties) = EmotionRules(p.getProperty("confidence.min").toDouble(),
            p.getProperty("event.expiry.ms").toLong(), p.getProperty("debounce.ms").toLong(),
            p.getProperty("cooldown.ms").toLong(), p.getProperty("minimum.dwell.ms").toLong(),
            p.getProperty("stable.window.ms").toLong(), p.getProperty("stable.gap.ms").toLong(),
            p.getProperty("startled.max.ms").toLong(), p.getProperty("concerned.max.ms").toLong(),
            p.getProperty("relief.dwell.ms").toLong(), p.getProperty("data.expiry.ms").toLong())
    }
}
