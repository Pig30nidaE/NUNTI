package ai.nunti.tts

import java.nio.file.Files
import java.nio.file.Path
import java.time.Instant
import java.util.Base64
import java.util.Properties

/** Receives lossless projections of real SERVER/AVATAR JSON fixtures from verify.py. */
fun main(args: Array<String>) {
    val values = Properties().apply { Files.newInputStream(Path.of(args.single())).use { load(it) } }
    fun get(prefix: String, key: String): String = String(Base64.getDecoder().decode(values.getProperty("$prefix.$key")), Charsets.UTF_8)
    fun optional(prefix: String, key: String) = get(prefix,key).ifBlank { null }
    fun profile(p: String) = SpeechContractBridge.fromVoiceProfile(WireVoiceProfile(get(p,"schemaVersion"),get(p,"voiceProfileId"),
        get(p,"locale"),get(p,"persona"),get(p,"speakingStyle"),optional(p,"preferredVoiceId"),get(p,"supportedControls").split(',').filter{it.isNotEmpty()}))
    fun emotion(p: String) = EmotionSnapshot(get(p,"emotionId"),get(p,"tripId"),get(p,"avatarId"),
        Emotion.valueOf(get(p,"emotion")),Instant.parse(get(p,"occurredAt")).toEpochMilli())
    val p="server-speech"
    val w=WireSpeechRequest(get(p,"schemaVersion"),get(p,"requestId"),get(p,"tripId"),get(p,"avatarId"),get(p,"text"),
        get(p,"voiceProfileId"),get(p,"emotion"),get(p,"tripPhase"),get(p,"priority"),get(p,"requestedAt"),get(p,"expiresAt"),
        get(p,"contentSource"),optional(p,"speechPurpose"),optional(p,"sourceEventId"),optional(p,"emotionId"))
    val serverAvatar=AvatarVoiceInput(w.avatarId,"nunti",w.voiceProfileId)
    val mapping=SpeechContractBridge.tryFromWire(w,serverAvatar,emotion("server-emotion"),SpeechEvidence(approvedText=true,allowMock=true))
    check(mapping is SpeechMappingResult.Accepted && mapping.speech.request.text==w.text)
    println("PASS actual SERVER SpeechRequest projection preserves purpose and text")
    val serverProfile=profile("server-profile")
    val resolved=VoiceProfileManager(listOf(serverProfile)).resolve(w.voiceProfileId,Emotion.RELIEVED,ProviderCapabilities())
    check(!resolved.fallback && resolved.locale=="ko-KR" && resolved.speakerId==null)
    println("PASS actual SERVER VoiceProfile resolves without fictional controls")
    val serverPrepared=SpeechRequestBuilder(VoiceProfileManager(listOf(serverProfile))).build(mapping.speech,ProviderCapabilities(),mapping.speech.request.requestedAt)
    check(serverPrepared.request.text==w.text && serverPrepared.request.emotionId==get("server-emotion","emotionId") && !serverPrepared.voice.fallback)
    println("PASS actual SERVER speech/profile/emotion are accepted together without rewriting")
    val missing=runCatching { SpeechRequestBuilder().build(mapping.speech.copy(snapshot=null),ProviderCapabilities(),mapping.speech.request.requestedAt) }.exceptionOrNull()
    check(missing is IllegalArgumentException && missing.message=="MISSING_EMOTION")
    println("PASS valid SERVER wire without emotion evidence is rejected for playback")
    val unsupported=SpeechContractBridge.tryFromWire(w.copy(emotion="FUTURE_EMOTION"),serverAvatar,null,
        SpeechEvidence(approvedText=true,allowMock=true))
    check(unsupported is SpeechMappingResult.Rejected)
    println("PASS future extended SERVER emotion token safely rejects without host exception")
    val avatarProfile=profile("avatar-profile")
    check(avatarProfile.voiceProfileId==VoiceProfile().voiceProfileId)
    check(!VoiceProfileManager(listOf(avatarProfile)).resolve(avatarProfile.voiceProfileId,Emotion.RELAXED,ProviderCapabilities()).fallback)
    println("PASS actual AVATAR profile matches stable default voice identity")
    val snapshot=emotion("avatar-emotion")
    val request=SpeechRequest("fixture-event",snapshot.tripId,snapshot.avatarId,"휴, 이제 좀 안심돼요.",snapshot.emotion,
        avatarProfile.voiceProfileId,TripPhase.DRIVING,Priority.NORMAL,snapshot.occurredAt,snapshot.occurredAt+5000,
        ContentSource.VERIFIED_EVENT_RESPONSE,snapshot.emotionId,get("avatar-emotion","triggeredByEventId"))
    val approved=ApprovedSpeech(request,AvatarVoiceInput(snapshot.avatarId,"nunti-v1",avatarProfile.voiceProfileId),snapshot,true)
    val prepared=SpeechRequestBuilder(VoiceProfileManager(listOf(avatarProfile))).build(approved,ProviderCapabilities(),request.requestedAt)
    check(prepared.voice.logicalStyle=="calm" && prepared.request.emotionId==snapshot.emotionId)
    println("PASS actual AVATAR EmotionSnapshot maps with synthetic approved matching request")
    val unrelated=approved.copy(avatar=AvatarVoiceInput(get("avatar-spec","avatarId"),get("avatar-spec","baseCharacterId"),get("avatar-spec","voiceProfileId")))
    val mismatch=runCatching { SpeechRequestBuilder().build(unrelated,ProviderCapabilities(),request.requestedAt) }.exceptionOrNull()
    check(mismatch is IllegalArgumentException && mismatch.message=="AVATAR_MISMATCH")
    println("PASS unrelated actual AVATAR samples cannot be silently joined")
    println("8 actual-fixture integration checks passed")
}
