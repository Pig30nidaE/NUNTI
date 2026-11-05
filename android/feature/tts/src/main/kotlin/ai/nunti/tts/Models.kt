package ai.nunti.tts

/** Local playback models; shared wire contracts remain owned by SERVER. */
enum class Emotion { NEUTRAL, RELAXED, CONCERNED, STARTLED, RELIEVED, JOYFUL }
enum class TripPhase { PRE_TRIP, DRIVING, STOPPED, POST_TRIP }
enum class Priority { LOW, NORMAL, HIGH }
enum class ContentSource { PRE_DRIVE_GREETING, VERIFIED_EVENT_RESPONSE, USER_INITIATED, POST_DRIVE_REPORT }
enum class EngineMode { ON_DEVICE, HYBRID, SERVER, LOCAL_FILE }
enum class Control { LOCALE, SPEAKER, RATE, PITCH, EMOTION }
data class AvatarVoiceInput(val avatarId: String, val baseCharacterId: String,
    val voiceProfileId: String? = null, val persona: String? = null, val voiceStyleHint: String? = null)
data class EmotionSnapshot(val emotionId: String, val tripId: String, val avatarId: String,
    val emotion: Emotion, val occurredAt: Long)
data class VoiceProfile(val voiceProfileId: String = "nunti-default-v1", val locale: String = "ko-KR",
    val preferredVoiceId: String? = null, val baseSpeakingStyle: String = "warm",
    val supportedControls: Set<Control> = setOf(Control.LOCALE), val fallbackMode: EngineMode = EngineMode.ON_DEVICE)
data class ProviderCapabilities(val locales: Set<String> = setOf("ko-KR"),
    val verifiedSpeakerIds: Set<String> = emptySet(), val controls: Set<Control> = setOf(Control.LOCALE))
data class AppliedVoiceProfile(val requestedProfileId: String?, val profileId: String,
    val locale: String, val speakerId: String?, val logicalStyle: String,
    val appliedControls: Set<Control>, val ignoredControls: Set<Control>, val fallback: Boolean)
data class SpeechRequest(val requestId: String, val tripId: String, val avatarId: String,
    val text: String, val emotion: Emotion, val voiceProfileId: String?, val tripPhase: TripPhase,
    val priority: Priority, val requestedAt: Long, val expiresAt: Long, val contentSource: ContentSource,
    val emotionId: String? = null, val sourceEventId: String? = null)
/** Trust is supplied by the authenticated integration boundary, never inferred from wire enum names. */
data class ApprovedSpeech(val request: SpeechRequest, val avatar: AvatarVoiceInput,
    val snapshot: EmotionSnapshot?, val contentVerified: Boolean)
data class PreparedSpeech(val request: SpeechRequest, val voice: AppliedVoiceProfile)
enum class SpeechStatus { QUEUED, STARTED, COMPLETED, CANCELLED, REJECTED, FAILED }
data class SpeechEvent(val requestId: String, val tripId: String, val status: SpeechStatus,
    val reason: String? = null, val appliedVoice: AppliedVoiceProfile? = null,
    val mode: EngineMode? = null, val startLatencyMs: Long? = null, val providerId: String? = null)
data class SpeechSource(val mode: EngineMode, val providerId: String)
interface SpeechClock { fun epochMs(): Long; fun monotonicMs(): Long }
fun interface Cancellation { fun cancel() }
/** Callbacks must run on the same serial executor as the queue. */
fun interface SpeechScheduler { fun after(delayMs: Long, action: () -> Unit): Cancellation }
