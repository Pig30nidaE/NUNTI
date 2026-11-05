#!/usr/bin/env python3
"""Recheck saved MVP source, WAVs, APK assets and actual runtime evidence offline."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

from verify_bundle import verify as verify_bundle
from verify_runs import verify as verify_generation_runs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = ROOT / ".local/journey-mvp"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def main():
    bundle = read(WORK / "bundle/bundle.json")
    manifest = read(WORK / "bundle/voice/manifest.json")
    clips = {clip["clipId"]: clip for clip in manifest["clips"]}
    report = {"checkedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "Saved artifact/evidence verification only. Does not contact the device, infer speech, or assess human taste.",
        "status": "FAIL"}
    source = verify_bundle(WORK, 8, 8)
    generation = verify_generation_runs()
    raw = [json.loads(line) for line in (HERE / "runtime-04/runtime-events.jsonl").read_text().splitlines()]
    requests = {e["requestId"]: e for e in raw if e["kind"] == "MVP_SPEECH_REQUEST"}
    completed = {}
    for event in raw:
        if event["kind"] != "MVP_SPEECH" or event["status"] != "COMPLETED":
            continue
        request = requests[event["requestId"]]
        clip = clips[request["clipId"]]
        require(all(request[key] == clip[key] for key in ("characterId", "profileId", "audioSha256", "textSha256")), "Runtime/source clip mismatch")
        require(event["mode"] == "LOCAL_FILE" and event["providerId"] == manifest["providerId"] and event["profileId"] == clip["profileId"], "Runtime escaped the selected local voice")
        sequence = [e["status"] for e in raw if e["kind"] == "MVP_SPEECH" and e["requestId"] == event["requestId"]]
        require(sequence == ["QUEUED", "STARTED", "COMPLETED"], "Incomplete playback lifecycle")
        completed[clip["clipId"]] = event["requestId"]
    require(set(completed) == set(clips) and len(completed) == 24, "Not all 24 source clips completed")
    boundaries = [e for e in raw if e["kind"] == "MVP_BOUNDARY_TESTS"]
    require(any(e["passed"] == e["total"] == 10 and all(c["passed"] is True for c in e["checks"]) for e in boundaries), "Android boundary checks did not pass")
    saved = [e for e in raw if e["kind"] == "MVP_SAVED"]
    require({e["characterId"] for e in saved} == {c["characterId"] for c in bundle["characters"]}, "Missing saved case")
    require(any(e["kind"] == "MVP_RESTORED" and e["stage"] == "ARRIVED" and e["collectedCount"] == 8 and e["automaticSpeech"] is False for e in raw), "Eight-case restore not observed")
    # Keep the original failed whole-run verdict. The final APK has separate targeted retests.
    old_run = read(HERE / "runtime-04/verification.json")
    require(old_run["status"] == "FAIL" and old_run["error"] == "Cancellation differs", "Historical verdict changed")
    expected = {
        "assets-runtime-02": "PASS_THREE_ASSET_NEGATIVES",
        "drive-runtime-02": "PASS_ACTUAL_D_ZERO_CANCEL_REJECT_AND_P_SILENT_RETURN",
        "stop-runtime-01": "PASS_ACTIVE_AND_PENDING_STOP_REGRESSIONS",
        "lifecycle-runtime-01": "PASS_LIFECYCLE_AND_VISUAL_CAPTURE",
        "audio-runtime-01": "CAPTURED_AUTHENTICATED_PCM_AND_MEASURED",
    }
    for directory, status in expected.items():
        require(read(HERE / directory / "verification.json")["status"] == status, directory + " did not pass")
    final_apk = WORK / "Nunti-Journey-MVP-debug.apk"
    delivery = read(HERE / "delivery-observation.json")
    require(delivery["sourceApkSha256"] == read(WORK / "delivered-apk.json")["sha256"] == sha(final_apk), "Delivered APK changed")
    require(delivery["defaultCollectionEmpty"] is True and delivery["userLastGate"]["visible"] is True and delivery["userLastGate"]["quietConfirmed"] is False, "User test state was not prepared")
    for namespace in ("journey-mvp", "journey-mvp-validation"):
        require(delivery["installedWavSha256"][namespace] == {key: clip["audioSha256"] for key, clip in clips.items()}, "Installed/source WAV mismatch")
    with zipfile.ZipFile(final_apk) as archive:
        expected_files = {"assets/journey-mvp/" + str(p.relative_to(WORK / "bundle")): p for p in (WORK / "bundle").rglob("*") if p.is_file()}
        require({name for name in archive.namelist() if name.startswith("assets/journey-mvp/")} == set(expected_files), "Debug asset set changed")
        require(all(archive.read(name) == path.read_bytes() for name, path in expected_files.items()), "Debug/source bytes changed")
    release = ROOT / "android/build/app/outputs/apk/release/app-release-unsigned.apk"
    with zipfile.ZipFile(release) as archive:
        require(not any(name.startswith("assets/journey-mvp/") for name in archive.namelist()), "MVP assets leaked into release")
    require("BUILD SUCCESSFUL" in (HERE / "android-build.log").read_text(), "Build/lint did not pass")
    core = (HERE / "tts-core-tests.log").read_text()
    for phrase in ("62 tests passed; 0 failed", "33 local voice tests passed", "8 actual-fixture integration checks passed", "24 actual WAV catalog checks passed"):
        require(phrase in core, "Core test evidence missing: " + phrase)
    require(read(HERE / "asr/verification.json")["status"] == "FILE_INTEGRITY_AND_TWELVE_NEW_MVP_WAV_ONE_PASS_ASR_VERIFIED", "New-case ASR evidence missing")
    report.update(status="PASS_OFFLINE_MVP_DELIVERY_EVIDENCE", bundleId=bundle["bundleId"],
        generation=source, actualGenerationRuns=generation, androidCompletedClipRequestIds=completed,
        androidBoundaryChecks=10, finalTargetedRuns=expected,
        fullRunScope="runtime-04 completed all 24 clips and eight saved/restored identities on the archived APK. Its HOME background check failed and is preserved. The final APK adds full-queue stop and was retested for stop, Settings background, D/P, asset negatives and eight-case visual selection.",
        fullRunApk=read(HERE / "runtime-04-source.json"), finalApkSha256=sha(final_apk),
        debugMvpAssetFiles=len(expected_files), releaseMvpAssetFiles=0, installedWavHashesChecked=48,
        userStateNamespace="journey-mvp", validationStateNamespace="journey-mvp-validation",
        notVerified=["Anna API and Android model inference", "Physical vehicle/device validation", "Human cuteness, collectibility or listening approval", "Driving-habit improvement", "Precise audible cancellation latency", "Every body/expression combination"],
        evidenceSha256={str((HERE / directory / "verification.json").relative_to(ROOT)): sha(HERE / directory / "verification.json") for directory in expected})
    (HERE / "delivery-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "characters": 8, "completedClips": len(completed), "finalApkSha256": report["finalApkSha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
