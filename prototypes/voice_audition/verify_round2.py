"""Check local audition files and decisions. No network, decoding service, or inference."""
from __future__ import annotations

import array
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
import wave

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOHEE = ROOT / "prototypes/qwen_sohee_audition"
REPORT = HERE / "evidence/pm-round2-verification-current.json"
ANNA_ID = "uyVNoMrnUku1dZyVEXwD"
ANNA_SOURCE = "prototypes/voice_audition/commercial/elevenlabs-anna-common-arrival.mp3"
ANNA_SOURCE_SHA = "5b7d8821b2d714789a54c0de0ba4005d373beb7871094e64051d752ceca649fb"
MP3_NAMES = (
    "elevenlabs-anna-common-arrival", "elevenlabs-stella-common-arrival", "elevenlabs-anna-journey",
)
SOHEE_NAMES = ("normal-hello", "normal-arrival", "small-smile-hello", "small-smile-arrival")
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, condition: bool) -> None:
    checks.append({"name": name, "passed": bool(condition)})


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[tuple[str, str]] = []
        self.audio: list[dict] = []
        self.ids: set[str] = set()
        self.script_count = 0
        self.autoplay_count = 0
        self.active_content_count = 0

    def handle_starttag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        values = dict(attributes)
        self.script_count += tag == "script"
        self.autoplay_count += "autoplay" in values
        self.active_content_count += tag in {"form", "iframe", "object", "embed"}
        self.active_content_count += sum(name.startswith("on") for name in values)
        if tag == "audio":
            self.audio.append(values)
        if values.get("id"):
            self.ids.add(values["id"])
        for attribute in ("href", "src"):
            if values.get(attribute):
                self.refs.append((attribute, values[attribute]))


def verify_mp3s() -> list[dict]:
    results = []
    for name in MP3_NAMES:
        meta_path = HERE / "commercial" / (name + ".json")
        record = read_json(meta_path)
        audio = meta_path.with_suffix(".mp3")
        actual_sha = sha(audio)
        actual_size = audio.stat().st_size
        check(name + ": file name", record["file"] == audio.name)
        check(name + ": audio SHA", actual_sha == record["audioSha256"])
        check(name + ": byte length", actual_size == record["bytes"] and actual_size > 0)
        check(name + ": original UTF-8 text SHA", hashlib.sha256(record["text"].encode("utf-8")).hexdigest() == record["textSha256"])
        check(name + ": MP3 metadata", record["format"] == "mp3")
        check(name + ": exact provider model remains undisclosed", record["modelId"] is None)
        check(name + ": anonymous and unpaid provenance", all(record[key] is False for key in ("downloadedWithApiKey", "accountCreated", "paidApiCall")))
        check(name + ": no product approval asserted", record["productUsageApproved"] is False)
        check(name + ": original download", record["postprocessing"] == "none; original provider download")
        results.append({"file": str(audio.relative_to(ROOT)), "audioSha256": actual_sha,
                        "bytes": actual_size, "metadataSha256": sha(meta_path),
                        "textSha256": record["textSha256"], "modelId": None})
    first, second = [read_json(HERE / "commercial" / (name + ".json")) for name in MP3_NAMES[:2]]
    check("Commercial common samples use the same exact text", first["text"] == second["text"] and first["textSha256"] == second["textSha256"])
    return results


def verify_selection() -> dict:
    selected = read_json(HERE / "selected-voice.json")
    feedback = read_json(HERE / "user-feedback.json")
    public = read_json(HERE / "commercial/anna-public-voice-id.json")
    preferred = feedback["commercialRound2"]
    decision = feedback["commercialAccountDecision"]
    journey = read_json(HERE / "commercial/elevenlabs-anna-journey.json")
    prepared = read_json(ROOT / "prototypes/elevenlabs_voice/verification.json")
    check("Selected Anna pointer is the original common sample", selected["sourceAudio"] == preferred["audioPath"] == ANNA_SOURCE)
    check("Original selected Anna bytes match both decision records", selected["sourceAudioSha256"] == preferred["audioSha256"] == sha(ROOT / ANNA_SOURCE) == ANNA_SOURCE_SHA)
    check("Anna UI identity agrees with selected voice and feedback", selected["voiceId"] == preferred["voiceIdFromPublicUi"] == public["voiceId"] == journey["voiceIdFromPublicUi"] == ANNA_ID)
    check("Anna name agrees across selection records", selected["voiceName"] == preferred["preferred"] == public["voiceName"] == journey["voiceName"])
    check("Public model and authenticated access remain unverified", selected["modelId"] is None and public["modelId"] is None and public["apiAccessVerified"] is False and prepared["actualApiAccountAccessVerified"] is False)
    check("User account deferral is preserved", decision["status"] == "ACCOUNT_CONNECTION_DEFERRED_BY_USER" and decision["quote"] == selected["accountDecisionQuote"] == "지금은 계정 없이 진행")
    check("Account deferral agrees across preparation and journey", selected["accountDeferredByUser"] is True and journey["accountDeferredByUser"] is True and prepared["accountDeferredByUser"] is True)
    check("No authenticated API work is authorized", decision["additionalAuthenticatedApiCallsAuthorized"] is False and prepared["additionalApiCallsAuthorized"] is False)
    check("Selected casting does not claim production or API benchmark approval", selected["commercialApiBenchmarked"] is False and selected["productionReady"] is False and selected["accountAvailable"] is False)
    followup = selected["followupAudition"]
    journey_path = "prototypes/voice_audition/commercial/elevenlabs-anna-journey.mp3"
    check("Follow-up selection pointer matches actual new journey bytes", followup["audioPath"] == journey_path and followup["audioSha256"] == journey["audioSha256"] == sha(ROOT / journey_path))
    latest = feedback["journeySameTextComparison"]
    check("Journey feedback still prefers Anna and preserves the compared original", followup["status"] == latest["status"] == "USER_STILL_PREFERS_ANNA" and followup["feedbackQuote"] == latest["quote"] == "Anna가 여전히 가장 가까움" and latest["audioPath"] == journey_path and latest["audioSha256"] == sha(ROOT / journey_path))
    check("Preferred Anna remains an unverified API model without Android integration", followup["modelId"] is None and followup["androidIntegrated"] is False)
    check("Prototype continuation does not select Sohee as preferred casting", feedback["prototypeContinuation"]["status"] == "PROTOTYPE_GENERATION_CONTINUATION_AUTHORIZED" and selected["localDynamicGeneration"]["humanApprovalOfNewDirections"] is False and selected["accountFreeAlternative"]["preferredCastingRemains"] == "Anna")
    check("Rejected Base follow-up remains rejected", feedback["fixedReferenceFollowup"]["status"] == "REJECTED_FOR_PERCEIVED_UNNATURALNESS")
    return {"voiceId": ANNA_ID, "sourceAudio": ANNA_SOURCE, "sourceAudioSha256": sha(ROOT / ANNA_SOURCE),
            "accountDeferredByUser": True, "modelId": None,
            "verificationScope": "Agreement of saved user-decision records, not a new human evaluation"}


def verify_sohee() -> list[dict]:
    config = read_json(SOHEE / "config.json")
    lock = read_json(SOHEE / "model-lock.json")
    old_hashes = read_json(SOHEE / "verification.json")["restart"]["fileHashesAfter"]
    sentences = {entry["id"]: entry["text"] for entry in config["sentences"]}
    conditions = {entry["id"]: entry["instruct"] for entry in config["conditions"]}
    results = []
    for clip_id in SOHEE_NAMES:
        audio = SOHEE / "samples" / (clip_id + ".wav")
        metadata = audio.with_suffix(".json")
        record = read_json(metadata)
        condition, sentence = clip_id.rsplit("-", 1)
        text = sentences[sentence]
        check(clip_id + ": original metadata SHA preserved", sha(metadata) == old_hashes[str(metadata.relative_to(SOHEE))])
        check(clip_id + ": original WAV SHA preserved", sha(audio) == record["audioSha256"] == old_hashes[str(audio.relative_to(SOHEE))])
        check(clip_id + ": text and text SHA", record["text"] == text and record["textSha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest())
        check(clip_id + ": clip and file identity", record["clipId"] == clip_id and record["audioPath"] == audio.name)
        check(clip_id + ": model and source config", record["modelId"] == lock["modelId"] and record["revision"] == lock["revision"] and record["modelLockSha256"] == sha(SOHEE / "model-lock.json") and record["configSha256"] == sha(SOHEE / "config.json"))
        check(clip_id + ": preset and generation metadata", record["speaker"] == config["speaker"] == "Sohee" and record["speakerId"] == 2864 and record["languageId"] == 2064 and record["generation"] == config["generation"] and record["instruct"] == conditions[condition])
        check(clip_id + ": no reference or processing", record["referenceAudio"] is None and record["postprocessing"] == config["postprocessing"])
        with wave.open(str(audio), "rb") as source:
            header = {"channels": source.getnchannels(), "sampleWidthBytes": source.getsampwidth(),
                      "sampleRateHz": source.getframerate(), "frames": source.getnframes(),
                      "compression": source.getcomptype()}
            pcm = array.array("h", source.readframes(source.getnframes()))
        if sys.byteorder != "little":
            pcm.byteswap()
        clipped = sum(sample in {-32768, 32767} for sample in pcm)
        check(clip_id + ": actual PCM WAV header", (header["channels"], header["sampleWidthBytes"], header["sampleRateHz"], header["compression"]) == (1, 2, 24000, "NONE"))
        check(clip_id + ": actual PCM length and metadata", header["frames"] == len(pcm) == record["frames"] and record["channels"] == header["channels"] and record["sampleRateHz"] == header["sampleRateHz"] and abs(record["durationSeconds"] - len(pcm) / header["sampleRateHz"]) < 1e-9)
        check(clip_id + ": nonempty nonzero PCM without full-scale samples", bool(pcm) and any(pcm) and clipped == 0)
        results.append({"clipId": clip_id, "audioSha256": sha(audio), "metadataSha256": sha(metadata),
                        "header": header, "fullScaleSamples": clipped,
                        "scope": "PCM file consistency only, not perceived clipping or quality"})
    return results


def verify_html() -> dict:
    path = HERE / "round2-listen.html"
    body = path.read_text(encoding="utf-8")
    page = Page()
    page.feed(body)
    local = []
    external_links = []
    for attribute, value in page.refs:
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            check("HTML external reference is an HTTPS hyperlink: " + value, attribute == "href" and parsed.scheme == "https")
            external_links.append(value)
            continue
        target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
        check("HTML local reference exists: " + value, target.is_relative_to(ROOT) and target.exists())
        if not parsed.path and parsed.fragment:
            check("HTML fragment exists: " + value, parsed.fragment in page.ids)
        local.append(value)
    sources = {audio.get("src") for audio in page.audio}
    required = {"commercial/" + name + ".mp3" for name in MP3_NAMES}
    required.update("../qwen_sohee_audition/samples/" + name + ".wav" for name in SOHEE_NAMES if name.startswith("small-smile"))
    check("HTML contains all three commercial and two Sohee preview sources", required <= sources)
    check("HTML audio controls wait for user input", all("controls" in audio and audio.get("preload") == "none" for audio in page.audio))
    check("HTML has zero scripts", page.script_count == 0)
    check("HTML has zero autoplay attributes", page.autoplay_count == 0)
    check("HTML has no forms, embedded apps, or event handlers", page.active_content_count == 0)
    check("HTML links to the default Sohee comparison", "../qwen_sohee_audition/listen.html" in local)
    return {"fileSha256": sha(path), "audioControls": len(page.audio),
            "scriptCount": page.script_count, "autoplayCount": page.autoplay_count,
            "localReferences": local, "externalHyperlinksNotFetched": external_links,
            "browserPlaybackVerifiedByThisTool": False}


def main() -> int:
    protected = [HERE / "selected-voice.json", HERE / "user-feedback.json",
                 HERE / "commercial/anna-public-voice-id.json", SOHEE / "config.json",
                 SOHEE / "model-lock.json", SOHEE / "verification.json",
                 ROOT / "prototypes/elevenlabs_voice/verification.json"]
    protected += [HERE / "commercial" / (name + suffix) for name in MP3_NAMES for suffix in (".mp3", ".json")]
    protected += [SOHEE / "samples" / (name + suffix) for name in SOHEE_NAMES for suffix in (".wav", ".json")]
    before = {str(path.relative_to(ROOT)): sha(path) for path in protected}
    result = {"checkedAt": datetime.now(timezone.utc).isoformat(),
              "tool": str(Path(__file__).resolve().relative_to(ROOT)),
              "providerRequestsPerformed": 0, "modelLoads": 0, "newInferences": 0,
              "humanQualityEvaluatedByThisTool": False, "exactApiModelVerified": False,
              "doesNotProve": ["naturalness", "cuteness", "phonetic accuracy", "perceptual speaker identity",
                               "exact public-demo model", "API entitlement", "production readiness", "browser playback"]}
    for name, operation in (("commercialMp3s", verify_mp3s), ("selection", verify_selection),
                            ("soheePcmFiles", verify_sohee), ("html", verify_html)):
        try:
            result[name] = operation()
        except (OSError, ValueError, KeyError, TypeError, wave.Error) as error:
            checks.append({"name": name + ": readable complete artifact", "passed": False,
                           "error": type(error).__name__, "detail": str(error)})
    after = {str(path.relative_to(ROOT)): sha(path) for path in protected}
    check("Protected originals and existing reports unchanged during verification", before == after)
    result["protectedFileHashesBefore"] = before
    result["protectedFileHashesAfter"] = after
    result["checks"] = checks
    result["checksPassed"] = sum(item["passed"] for item in checks)
    result["checksTotal"] = len(checks)
    success = all(item["passed"] for item in checks)
    result["status"] = "파일정합성 통과" if success else "파일정합성 확인 실패"
    result["statusCode"] = "PASSED_OFFLINE_FILE_CONSISTENCY" if success else "FAILED_OFFLINE_FILE_CONSISTENCY"
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "checksPassed": result["checksPassed"],
                      "checksTotal": result["checksTotal"], "report": str(REPORT.relative_to(ROOT)),
                      "providerRequestsPerformed": 0}, ensure_ascii=False, indent=2))
    if not success:
        print(json.dumps([item for item in checks if not item["passed"]], ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
