package ai.nunti.score.live

enum class LinkState { IDLE, CONNECTED, SUBSCRIBED, DISCONNECTED, FAILED }

/** 외부 서비스(Vehicle/Navi) 연결 상태. 상태 판단은 [state] 로 하고, [detail] 은 화면에 덧붙일 오류 설명이다. */
data class LinkStatus(val state: LinkState, val detail: String? = null) {
    val text: String
        get() = when (state) {
            LinkState.IDLE -> "대기"
            LinkState.CONNECTED -> "연결됨"
            LinkState.SUBSCRIBED -> "구독 요청 완료"
            LinkState.DISCONNECTED -> "연결 끊김"
            LinkState.FAILED -> "실패" + (detail?.let { ": $it" } ?: "")
        }
}

/** 화면 확인용 신호 한 줄. [value] 가 null 이면 미수신. */
data class SignalReading(val label: String, val value: String?)
