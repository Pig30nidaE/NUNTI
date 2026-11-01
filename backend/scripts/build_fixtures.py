"""Deterministically create fixtures. No scoring, generation or emotion algorithm."""

from copy import deepcopy

from export_contracts import ROOT, write_json

MOCK = {"kind": "MOCK", "provider": "nunti-fixture", "version": "1"}
STAMP = "2026-11-01T03:00:00Z"


def samples(trip_id):
    trip = {"schemaVersion": "1.0", "tripId": trip_id, "startedAt": STAMP, "syncConsent": True}
    route = {
        "schemaVersion": "1.0",
        "routeId": "route-mock",
        "routeRevision": 1,
        "collectedAt": STAMP,
        "source": MOCK,
        "routeOption": "RECOMMENDED",
        "distanceMeters": 5000,
        "estimatedDurationSeconds": 900,
        "roadTypeRatios": {"urban": 0.9, "unknown": 0.1},
        "regionTags": [],
        "scenicTags": [],
        "featureEvidence": {
            "roadTypeRatios": {
                "source": MOCK,
                "verificationStatus": "VERIFIED",
                "confidence": 1.0,
                "validity": "VALID",
                "observedAt": STAMP,
            }
        },
    }
    avatar = {
        "schemaVersion": "1.0",
        "avatarId": "avatar-mock",
        "baseCharacterId": "nunti",
        "routeId": "route-mock",
        "routeRevision": 1,
        "generationSeed": "mock-seed-001",
        "ruleVersion": "mock-1",
        "assetVersion": "mock-1",
        "paletteId": "mint",
        "outfitId": "city",
        "accessoryIds": [],
        "themeId": "urban",
        "voiceProfileId": "voice-mock",
        "generationExplanation": "고정 Mock 아바타. 생성 알고리즘 결과 아님.",
    }
    event = {
        "schemaVersion": "1.0",
        "eventId": "event-brake",
        "tripId": trip_id,
        "eventType": "HARD_BRAKING",
        "occurredAt": "2026-11-01T03:05:00Z",
        "severity": "MEDIUM",
        "confidence": 0.9,
        "verificationStatus": "VERIFIED",
        "source": MOCK,
        "correlationId": "incident-mock",
        "recoveryOfEventId": None,
    }
    emotion = {
        "schemaVersion": "1.0",
        "emotionId": "emotion-worried",
        "tripId": trip_id,
        "avatarId": "avatar-mock",
        "emotion": "CONCERNED",
        "intensity": 0.5,
        "triggeredByEventId": "event-brake",
        "occurredAt": "2026-11-01T03:05:01Z",
        "confidence": 0.9,
    }
    voice = {
        "schemaVersion": "1.0",
        "voiceProfileId": "voice-mock",
        "locale": "ko-KR",
        "persona": "COMPANION",
        "speakingStyle": "CALM",
        "preferredVoiceId": None,
        "supportedControls": [],
    }
    report = {
        "schemaVersion": "1.0",
        "tripId": trip_id,
        "overallScore": None,
        "dataCoverage": {
            "status": "INSUFFICIENT",
            "evaluatedSeconds": 300,
            "totalSeconds": 900,
            "ratio": 0.333333,
            "unavailableSignals": ["LEAD_VEHICLE_DISTANCE"],
        },
        "finalText": "[MOCK] 중간에 놀란 순간이 있었어요. 확인하지 못한 정보도 있어요.",
        "evidenceEventIds": ["event-brake"],
        "generatedAt": "2026-11-01T03:15:00Z",
    }
    speech = {
        "schemaVersion": "1.0",
        "requestId": "speech-mock",
        "tripId": trip_id,
        "avatarId": "avatar-mock",
        "text": report["finalText"],
        "voiceProfileId": "voice-mock",
        "emotion": emotion["emotion"],
        "tripPhase": "POST_TRIP",
        "priority": "NORMAL",
        "requestedAt": "2026-11-01T03:15:01Z",
        "expiresAt": "2026-11-01T03:16:01Z",
        "contentSource": "MOCK",
        "speechPurpose": "POST_DRIVE_REPORT",
        "sourceEventId": None,
        "emotionId": emotion["emotionId"],
    }
    return dict(
        zip(
            (
                "TripCreate",
                "RouteSnapshot",
                "AvatarSpec",
                "DrivingEvent",
                "EmotionSnapshot",
                "VoiceProfile",
                "TripReport",
                "SpeechRequest",
            ),
            (trip, route, avatar, event, emotion, voice, report, speech),
            strict=True,
        )
    )


def operation(method, path, body=None, fault=None):
    result = {"method": method, "path": path, "expectedStatus": 200}
    if body is not None:
        result["body"] = deepcopy(body)
    if fault:
        result["transportFault"] = fault
    return result


def main():
    base = samples("trip-mock")
    base["EventBatch"] = {"schemaVersion": "1.0", "events": [base["DrivingEvent"]]}
    base["EmotionBatch"] = {"schemaVersion": "1.0", "emotions": [base["EmotionSnapshot"]]}
    invalid_field = {
        "RouteSnapshot": ("routeRevision", "1"),
        "AvatarSpec": ("generationSeed", 123),
        "DrivingEvent": ("confidence", 1.1),
        "EmotionSnapshot": ("intensity", -1),
        "VoiceProfile": ("supportedControls", "pitch"),
        "SpeechRequest": ("tripPhase", "FLYING"),
        "TripReport": ("overallScore", 101),
        "TripCreate": ("syncConsent", False),
        "EventBatch": ("events", []),
        "EmotionBatch": ("emotions", []),
    }
    for name, value in base.items():
        directory = ROOT / "contracts/v1/examples"
        write_json(directory / f"{name}.valid.json", value)
        missing = deepcopy(value)
        del missing["schemaVersion"]
        write_json(directory / f"{name}.missing.json", missing)
        invalid = deepcopy(value)
        key, bad = invalid_field[name]
        invalid[key] = bad
        write_json(directory / f"{name}.invalid.json", invalid)

    names = [
        ("01-urban", "도심 단거리"),
        ("02-highway", "고속도로 중심 장거리"),
        ("03-coastal", "해안 특징 확인"),
        ("04-missing-data", "데이터 일부 누락"),
        ("05-reroute", "주행 중 경로 변경"),
        ("06-braking", "급제동 이벤트"),
        ("07-recovery", "안정 주행으로 감정 회복"),
        ("08-duplicate", "이벤트 중복 전달"),
        ("09-reconnect", "연결 실패와 응답 유실 후 재전송"),
        ("10-report", "종료 리포트 조회"),
    ]
    for name, title in names:
        data = samples(f"trip-{name}")
        route = data["RouteSnapshot"]
        if name == "02-highway":
            route.update(
                routeOption="HIGHWAY",
                distanceMeters=320000,
                estimatedDurationSeconds=14400,
                roadTypeRatios={"highway": 0.85, "urban": 0.1, "unknown": 0.05},
            )
        if name == "03-coastal":
            route["scenicTags"] = ["COASTAL"]
            route["featureEvidence"]["scenicTags.COASTAL"] = deepcopy(
                route["featureEvidence"]["roadTypeRatios"]
            )
        if name == "04-missing-data":
            for key in ("distanceMeters", "estimatedDurationSeconds", "roadTypeRatios"):
                route.pop(key)
            route["featureEvidence"] = {}
            route["routeOption"] = "HIGHWAY"  # Does not imply any measured ratio.
        trip_id = data["TripCreate"]["tripId"]
        path = f"/v1/trips/{trip_id}"
        event_batch = {"schemaVersion": "1.0", "events": [data["DrivingEvent"]]}
        emotion_batch = {"schemaVersion": "1.0", "emotions": [data["EmotionSnapshot"]]}
        steps = [
            operation("POST", "/v1/trips", data["TripCreate"]),
            operation("PUT", path + "/route", route),
            operation("PUT", path + "/avatar", data["AvatarSpec"]),
        ]
        if name == "05-reroute":
            updated_route = deepcopy(route)
            updated_route.update(routeId="route-rerouted", routeRevision=2)
            updated_avatar = deepcopy(data["AvatarSpec"])
            updated_avatar.update(routeId="route-rerouted", routeRevision=2, themeId="rural")
            steps.extend(
                [
                    operation("PUT", path + "/route", updated_route),
                    operation("PUT", path + "/avatar", updated_avatar),
                ]
            )
        steps.extend(
            [
                operation("POST", path + "/events", event_batch),
                operation("POST", path + "/emotions", emotion_batch),
            ]
        )
        if name == "07-recovery":
            recovery = deepcopy(data["DrivingEvent"])
            recovery.update(
                eventId="event-recovered",
                eventType="STABLE_DRIVING",
                severity="INFO",
                occurredAt="2026-11-01T03:10:00Z",
                recoveryOfEventId="event-brake",
            )
            calm = deepcopy(data["EmotionSnapshot"])
            calm.update(
                emotionId="emotion-relieved",
                emotion="RELIEVED",
                intensity=0.7,
                occurredAt="2026-11-01T03:10:01Z",
                triggeredByEventId="event-recovered",
            )
            steps.extend(
                [
                    operation(
                        "POST", path + "/events", {"schemaVersion": "1.0", "events": [recovery]}
                    ),
                    operation(
                        "POST", path + "/emotions", {"schemaVersion": "1.0", "emotions": [calm]}
                    ),
                ]
            )
            data["EmotionSnapshot"] = calm
            data["SpeechRequest"].update(emotion=calm["emotion"], emotionId=calm["emotionId"])
            data["TripReport"].update(
                finalText="[MOCK] 중간에는 놀랐지만 다시 편안해졌어요. 함께해 줘서 고마워요.",
                evidenceEventIds=["event-brake", "event-recovered"],
            )
        if name == "08-duplicate":
            steps.append(operation("POST", path + "/events", event_batch))
        if name == "09-reconnect":
            steps[3]["transportFault"] = "before_send"
            steps[4]["transportFault"] = "after_commit"
        data["SpeechRequest"]["text"] = data["TripReport"]["finalText"]
        steps.extend(
            [
                operation("PUT", path + "/report", data["TripReport"]),
                operation("GET", path + "/report"),
                operation("GET", path + "/events"),
                operation("GET", path + "/emotions"),
                operation("GET", path),
            ]
        )
        write_json(
            ROOT / "backend/nunti/mock_data" / f"{name}.json",
            {
                "mock": True,
                "scenarioId": name,
                "title": title,
                "disclaimer": (
                    "Synthetic fixtures; not actual Pleos API responses. No scoring rules implied."
                ),
                "contracts": data,
                "steps": steps,
            },
        )


if __name__ == "__main__":
    main()
