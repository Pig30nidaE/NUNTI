# 여정별 수집형 캐릭터의 서버·저장·계약 제안

2026-11-02, Asia/Seoul. SERVER worktree `/Users/pig30nidae/NUNTI/.worktrees/server`, branch `codex/server-next`, 조사 HEAD `ebde9027f97f56f80bf8262c1200dbbb92827483`.

이 문서는 설계 제안이다. 제품 코드, 서비스, DB, wire 1.0, 공통 host·Gradle, 복원 증거를 변경하지 않았다. 외부 생성·음성 서비스 호출, 배포, 결제도 하지 않았다. 외부 payload·담당 협의는 사용자 지시에 따라 보류한다.

제품 기준은 PM의 [최신 여정 캐릭터 요구](/Users/pig30nidae/NUNTI/docs/product/journey-character-brief.md)다. 목적지·경로·목적지 특성·방문 목적은 새 캐릭터의 창작 재료다. 귀여움과 소장 가치는 사용자 평가로 확인해야 한다. ID나 생성 해시가 다르다는 사실만으로 달성했다고 판정하지 않는다.

## 사용자 선택 반영: C · 반투명 기념 오브젝트

사용자가 선택한 C를 아트 기준으로 고정한다. 여정의 기억은 형태·내부 무늬·빛으로 표현한다. 아래 A/B/C 구조 비교는 서버 처리 방식에 대한 비교이며 아트 방향의 재선택이 아니다.

- 생성 job과 provenance에 C의 아트 규칙 버전을 고정하고, 선택 결과의 manifest에는 외피·내부 무늬·빛 레이어와 재질·합성 방식·호환 renderer 버전을 연결하도록 제안한다. 세부 2.5D 규격은 AVATAR가 정하고 SERVER는 실제 자산·digest·버전을 보존한다. seed만으로 반투명 표현을 재생성하지 않는다.
- 기억 모티브는 사용자가 동의한 최소 의미 태그에서 가져온다. 내부 무늬에 실제 이동 궤적·정밀 위치를 자동 새기지 않으며, 빛의 세기를 운전 점수·위험도·희귀 보상으로 해석하지 않는다. 삭제 범위에는 기억을 담은 파생 자산과 썸네일도 포함한다.
- 첫 구현은 선택한 형태·무늬·빛 구성을 그대로 수집한다. 추후 도착 후 기억을 더하는 기능은 별도 불변 memory revision으로 설계하고 characterId와 음성 정체성을 유지한다. 재전송·reroute·늦은 생성 완료로 기억 장식을 중복 추가하지 않는다.
- TTS에는 C에 맞는 성격·음성 레시피 참조를 전달하되 실제 음향 제어 여부는 TTS가 검증한다. 반짝임·빛 변화의 재생은 로컬 차량·표시 정책이 결정하고 서버 완료 이벤트가 실행하지 않는다.

추가 수용 기준은 밝고 어두운 배경에서 얼굴·윤곽이 보이는지 AVATAR가 확인하고, 앱 재시작·오프라인 복원 뒤 동일 manifest와 자산으로 외피·내부 무늬·빛 구성이 유지되는지 통합 검사하는 것이다. 미지원 renderer에서는 검수된 C 방향의 정적 대체 자산을 사용한다. 새 이미지·외부 생성 호출은 PM 소유이며 이번 보완에서는 실행하지 않았다.

## 제안의 핵심과 사용자 흐름

앱이 여정 시작 시 캐릭터 ID와 생성 요청 ID를 먼저 영속화한다. 검수 자산과 레시피로 오프라인에서도 새 캐릭터를 준비하고, 향후 별도 동의를 받은 원격 생성은 같은 요청에 연결된 비동기 작업으로 추가한다. 캐릭터 선택, 주행 중 표시·발화, 도착 후 컬렉션 저장은 별도 단계다.

다음은 제안 인터페이스의 의사코드이며 기존 앱 API가 아니다.

```text
journey = localStore.beginJourney()                 // 새 tripId와 생성 ID를 한 번만 저장
ticket = characters.prepare(journey, creativeTags) // 로컬 후보, seed, 레시피 버전 보존
preview.show(ticket.localCandidate)
if userAllowsRemoteGeneration:
    jobs.submitSameRequest(ticket)                  // 비동기, 출발은 기다리지 않음
onUserSelectionWhileParked(candidate):
    localStore.activate(candidate.visualAndVoice)   // 검증된 묶음 하나를 원자적으로 고정
onDeparture():
    localStore.freezeActiveCharacter()             // 미선택이면 준비된 로컬 후보 사용
onArrival():
    collection.offerSave(activeCharacter)           // 수집 조작은 도착 후
```

같은 경로의 다음 여정은 새 `tripId`, `characterId`, `generationId`, seed를 받는다. 같은 여정의 재시도·reroute·앱 재시작은 저장된 ID와 선택 결과를 재사용한다. 경로 변경이 생성 요청을 새로 만들거나 얼굴·목소리를 교체해서는 안 된다. 명시적 재추첨은 첫 구현 범위에서 제외한다.

출발 후 도착한 원격 후보는 준비 완료로만 저장한다. 현재 캐릭터와 TTS를 바꾸거나 자동 발화하지 않는다. 최초 구현은 출발 전에 확정된 캐릭터를 도착 후 그대로 수집한다. 늦은 후보의 별도 소장·다음 여정 사용은 추후 제품 정책으로 정하며 자동 추가하지 않는다.

## 기존 구현에서 확인한 사실

| 범위 | 현재 동작과 한계 | 소스 근거 |
| --- | --- | --- |
| API·저장 | token→principal 소유자 분리, 명시적 syncConsent, 동일 내용 재전송, 충돌·원자적 배치가 있다. 생성 작업·자산 업로드·컬렉션 API는 없다 | [api.py](../../../backend/nunti/api.py)의 `owner`, `create_trip`, `put_avatar`; [store.py](../../../backend/nunti/store.py)의 `put`, `append` |
| 저장 수명 | records는 trips에 ON DELETE CASCADE로 연결된다. 기본 30일 뒤 주행과 하위 기록을 지운다. 이 구조로 장기 컬렉션을 보장할 수 없다 | [store.py](../../../backend/nunti/store.py)의 `initialize`, `purge_expired`; [config.py](../../../backend/nunti/config.py) |
| 계약 | schemaVersion 1.0, 추가 필드 거부, strict 타입이다. AvatarSpec에는 파츠 ID·voiceProfileId가 있으나 job·2.5D 파일 manifest·컬렉션·보관 동의는 없다 | [models.py](../../../backend/nunti/models.py), [v1 계약](../../../contracts/v1/README.md) |
| 생성·ID | avatarId는 baseCharacterId와 routeId의 해시다. seed는 동점 후보 순위에만 쓰고 고정 identity의 의상·장식을 선택한다. 새 여정마다 다른 실루엣을 만드는 엔진은 아니다 | [AvatarEngine.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/AvatarEngine.kt)의 `generate`; [Assets.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/Assets.kt) |
| 복원 자료 | wire AvatarSpec은 compact projection이다. 로컬 후보·audit·rule/asset digest는 별도 자료다 | [AVATAR 협업 기록](../../coordination/avatar.md), [WireAdapter.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/WireAdapter.kt) |
| 음성 | 기본 nunti-default-v1과 전역 화자 정책이 있다. 현재 Pleos 어댑터는 locale을 적용하고 speakerId가 있으면 거부한다. rate/pitch/emotion 제어·PCM 반환 경로는 없다. Pleos 제품 전체의 불가능성을 뜻하지 않는다 | [VoiceProfiles.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/VoiceProfiles.kt), [Models.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/Models.kt), [PleosTtsProvider.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/PleosTtsProvider.kt), [TTS 기록](../../coordination/tts.md) |
| 동기화 | Python DemoOutbox는 요청을 SQLite에 보존하고 2xx 응답 때 제거하는 단일 FIFO 참조 예제다. Android HTTP client·Room·WorkManager와 원자적 inbox/outbox 연결은 없다 | [demo_outbox.py](../../../backend/nunti/demo_outbox.py), [통합 예제](../../architecture/integration.md), [복원 보고](../../handoff/restoration/2026-11-02/server.md) |

고정 identity·전역 동일 음성은 [기존 AVATAR/TTS 합의](../../coordination/avatar.md)의 과거 제품 선택이다. 서버의 baseCharacterId·voiceProfileId 타입 자체는 단일 값을 강제하지 않는다. 그러나 새 ID만 넣어도 현재 renderer·프로필 resolver가 새 외형과 음성을 지원하는 것은 아니다. 최신 요구에 맞춰 AVATAR/TTS가 이 선택을 바꿀 수 있다.

계속 유지할 제약은 로컬 반응의 서버 독립성, UNKNOWN 유지, 명시적 동의, 소유자 분리다. 원격 저장·조회·재전송으로 감정을 계산하거나 발화하지 않는다. 실제 차량·lifecycle·오디오 정책이 표시와 재생을 결정한다. `overallScore=null`과 `TripReport.finalText` 원문 보존도 유지한다.

## 가능한 구조의 비교

아래는 설계 스케치다. 새 프로토타입 실행 결과가 아니다.

| 구조 | 호출·상태 소유 | 장점 | 남는 문제 |
| --- | --- | --- | --- |
| A. 로컬 레시피·검수 파츠, 서버는 선택 결과 보관 | 앱이 생성·선택하고 동의된 컬렉션만 업로드 | 오프라인 시작, 재현·용량 통제 용이 | 실루엣·재질·성격 다양성을 검수 자산으로 확보해야 함. 현재 의상 교체만으로 부족 |
| B. 로컬 레시피 + 선택적 비동기 원격 후보 | 앱은 즉시 준비·활성 상태, 서버는 작업·자산·보관 소유 | 출발 독립성을 유지하며 전문 모델을 추후 연결 가능 | 늦은 완료, 품질 불합격, 철회, provider 불확정 응답 처리 필요 |
| C. 서버 생성 완료 후 캐릭터 배정 | 서버의 동기 생성 결과가 준비 조건 | 중앙 생성 통제가 단순 | 오프라인·실패·지연이 출발을 막아 요구에 부적합 |

B를 목표로 제안하되 첫 구현은 A와 B의 가짜 worker로 시작한다. 모델·외부 TTS 선정과 실호출은 별도 검증 후 결정한다. 기존 FastAPI와 SQLite 안에 job 상태를 먼저 설계한다. 초기 worker는 한 개로 제한하고 재시작 후 DB의 작업을 다시 읽는다. 메모리의 background task만으로 완료를 보장하지 않는다. 메시지 브로커·WebSocket·별도 마이크로서비스 도입은 초기 범위에서 제외한다.

## ID·불변 결과·선택의 경계

첫 설계에서는 journeyId를 별도로 만들지 않고 앱이 출발 전 생성한 tripId를 여정 ID로 쓴다. 원격 job을 위해 거짓 startedAt이나 주행 저장 동의를 만들어 기존 TripCreate를 호출하지 않는다. 새 job의 trip 참조는 서버에 업로드하지 않은 여정도 가리킬 수 있다.

| 식별자 | 생성·소유 규칙 |
| --- | --- |
| tripId | 앱이 새 여정 행동에서 한 번 생성. reroute는 기존 ID와 증가한 routeRevision 사용 |
| characterId | 앱이 여정 캐릭터를 예약할 때 비위치 UUID 등으로 생성. 처음에는 여정당 하나. v1 연결 시 같은 문자열을 avatarId에 명시적으로 매핑 |
| generationId | 앱이 원래 입력·seed와 함께 영속화. HTTP 재시도와 worker 실행 횟수에 따라 바꾸지 않음 |
| candidateId | 로컬·원격 후보별 ID. 요청과 결과 digest에 귀속 |
| characterRevision | 선택한 visual manifest·voice recipe 묶음의 불변 버전. 첫 구현은 선택 확정 후 revision 1 잠금 |
| assetId·sha256 | 소유자 범위 자산 ID와 실제 바이트 digest. 해시가 같아도 소유자 권한은 공유하지 않음 |
| collectionEntryId | 소유자와 characterId마다 하나. 중복 저장·도착으로 카드가 늘지 않음 |

앱은 tripId·characterId·generationId·seed·로컬 후보·활성 상태를 한 로컬 트랜잭션으로 준비한다. seed는 JSON 문자열이며 알고리즘·레시피·자산 버전과 함께 보존한다. 새 seed만으로 시각적 개별성을 보장할 수 없으므로 AVATAR의 novelty 판정이 별도로 필요하다.

원격 멱등 키는 `(principal, generationId)`다. 정규화한 원래 요청이 같으면 같은 작업 ID와 현재 상태를 반환한다. 내용이 다르면 409 `generation_conflict`다. 최초 수락 때 선택한 내부 recipe/model 버전은 job에 고정하고 배포 후에도 바꾸지 않는다. `(principal, tripId, initialSlot)` 유일 제약으로 두 창·장치의 초기 생성을 중복 수락하지 않는다. 충돌한 장치는 권한 확인 후 기존 작업을 조회한다.

정확히 한 번 보장할 대상은 서버의 결과 확정·캐릭터 선택·컬렉션 추가다. 외부 모델 호출·과금이 정확히 한 번 발생한다고 약속하지 않는다. 같은 seed로 원격 모델의 같은 바이트를 재생성한다고 보장하지도 않는다. 복원에는 확정 자산 바이트와 manifest가 필요하다.

## 계약 초안과 wire 1.0 영향

아래 이름과 `/v2` 경로, `schemaVersion="2.0-draft"`는 논의용이며 채택 미확정이다. 현재 API에 전송할 수 없다. 기존 `/v1`과 `contracts/v1`은 보존하고 별도 계약 묶음을 제안한다. v1에 필드를 덧붙이면 추가 필드 거부로 422가 된다.

| 제안 모델 | 핵심 필드·규칙 |
| --- | --- |
| CharacterGenerationCreate | generationId, tripId, characterId, 문자열 seed, recipeVersion, creativeContext, 선택 verifiedRouteRef, consentGrantId. 소유자는 인증에서만 결정 |
| CreativeContext | taxonomyVersion, destination category·purpose·motif 토큰, origin=USER_SELECTED/SYNTHETIC. 첫 버전은 자유 주소·GPS·목적지 원문·임의 프롬프트·외부 이미지 URL을 받지 않음 |
| GenerationJob | 요청 digest, 고정 recipe/model 버전, 상태 판별자와 상태별 payload. 준비 전 result나 실패 전 error를 동시에 담지 않음 |
| CharacterCandidate | candidateId, characterId, visualRecipeRef, voiceRecipeRef, assetManifestRef, qualityDecisionRef, provenanceRef. 검수 통과 뒤 선택 가능 |
| CharacterSpec | characterId, characterRevision, selectedCandidateId, visual/voice 참조, contentDigest, selectedAt. 외형과 음성 레시피를 같은 버전으로 묶음 |
| AssetManifest | format·renderer/rig 버전, 파일 역할·크기·MIME·sha256·assetId, 레이어·표정·동작 참조. 구체적 2.5D 규격은 AVATAR 소유 |
| VoiceRecipe | voiceRecipeId, 버전, locale, 성격/style, 희망 controls, 승인된 provider profile 참조, 명시적 fallback 참조. 실제 적용 결과와 구별 |
| CollectionEntry | 선택 characterId/revision, 보관 동의 참조, 저장 시각, 최소 기억 태그, 정책 버전·보관 수명. 원본 route·event·점수·리포트 원문은 복제하지 않음 |
| ConsentGrant | REMOTE_GENERATION 또는 COLLECTION_SYNC 목적, 정책 버전, 동의·철회 시각, 단조 증가 epoch. 주행 syncConsent로 대신하지 않음 |

다음은 합성 요청 예시다. 바다 모티브는 실제 해안 도로의 검증 근거가 아니다.

```json
{
  "schemaVersion": "2.0-draft",
  "generationId": "gen-demo-01",
  "tripId": "trip-demo-01",
  "characterId": "char-demo-01",
  "seed": "31728041",
  "recipeVersion": "journey-recipe-demo-1",
  "creativeContext": {
    "taxonomyVersion": "creative-demo-1",
    "destinationCategory": "WATERFRONT",
    "visitPurpose": "REST",
    "motifs": ["SHELL", "SOFT_WAVE"],
    "origin": "SYNTHETIC"
  },
  "consentGrantId": "grant-demo-01"
}
```

verifiedRouteRef를 쓰면 소유자·tripId·routeId·revision을 일치시킨다. 아직 동기화하지 않은 route를 VERIFIED로 가정하지 않는다. 첫 구현은 위처럼 합성 창작 태그만 사용한다. 생성 작업은 snapshot을 고정하고 reroute의 새 사실을 기존 job 입력에 덮어쓰지 않는다. 별도 최신 route 기록은 기존 계약대로 갱신할 수 있다.

| 제안 API | 응답·소유 의미 |
| --- | --- |
| PUT /v2/consents/{consentGrantId} | 인증된 소유자의 명시적 동의 행동·목적·정책 버전을 기록. 같은 요청은 duplicate. epoch는 서버가 부여하고 오래된 요청으로 철회 상태를 되돌리지 않음 |
| POST /v2/consents/{consentGrantId}/revoke | epoch 증가와 관련 작업 비공개를 원자적으로 처리. 다시 허용할 때는 새 동의 행동·grant 필요 |
| POST /v2/character-jobs | 요청·동의·입력 한도를 검사하고 durable job을 저장한 뒤 202와 generationId 반환. 중복은 동일 job 참조. 202는 캐릭터 생성 완료 ACK가 아님 |
| GET /v2/character-jobs/{generationId} | 소유자의 작업 상태·검수 완료 후보 참조. 앱의 준비 화면이나 예약된 복구에서 제한적으로 조회 |
| POST /v2/character-jobs/{generationId}/cancel | 같은 요청 반복 가능. 진행 중 provider 호출을 즉시 중단했다고 보장하지 않으며 결과 공개는 차단 |
| PUT /v2/characters/{characterId}/selection | 승인된 후보 하나를 revision 1로 고정. 같은 선택은 duplicate, 다른 선택은 409. 오프라인 선택은 나중에 같은 요청으로 동기화 |
| PUT /v2/collection/{characterId} | 선택 결과와 COLLECTION_SYNC 동의를 확인해 카드 하나 저장. 모델 완료만으로 수집 등록하지 않음 |
| GET /v2/collection | 순서 키와 opaque cursor로 조회. 삭제·수정 피드와 여러 장치 동기화 규격은 별도 확정 전까지 약속하지 않음 |
| DELETE /v2/characters/{characterId} | 카드·개인 자산·작업 결과를 즉시 비공개 처리하고 삭제 작업 ID 반환. 실제 제거 상태는 별도 조회 |

목록의 owner는 URL이나 JSON의 principal을 신뢰하지 않고 인증에서 결정한다. 각 조회·취소·선택·삭제·파일 다운로드에도 같은 소유자 검사를 적용한다. 선택 API는 임의 asset URL이나 임의 provider ID를 받아 활성화하지 않는다. 첫 로컬 후보 동기화는 검수된 내장 catalog ID·recipe 버전만 허용한다.

v1과의 관계는 다음처럼 제한한다.

- v1 RouteSnapshot의 featureEvidence에 CreativeContext를 넣지 않는다. 목적지·방문 목적은 실제 위험 이벤트나 검증된 GIS 사실이 아니다.
- v1 AvatarSpec의 baseCharacterId·themeId·generationExplanation에 2.5D JSON이나 파일 URL을 숨겨 넣지 않는다. 이 모델만으로 새 캐릭터를 복원할 수 없다.
- 향후 v1 병행 저장이 필요하면 검증된 adapter가 표현 가능한 compact projection만 만든다. characterId를 avatarId로 연결하고 새 경로 revision의 아바타를 저장할 때도 선택한 identity는 유지한다. 표현 불가능한 rig·voice는 명시적 미지원으로 처리한다.
- EmotionSnapshot이 기존 avatar 존재를 요구하는 순서, eventId/emotionId 재전송 규칙, SpeechRequest의 로컬 허가·만료·근거 규칙은 유지한다. 새 personality가 운전 감정을 덮어쓰지 않는다.
- v1 VoiceProfile의 희망 제어 목록을 실제 SDK 능력으로 해석하지 않는다. 새 voice recipe는 TTS의 검증된 profile registry를 통해서만 로컬 모델에 매핑한다.
- 기존 v1 전용 앱에는 새 자산을 전달해 렌더링을 기대하지 않는다. 새 기능 capability와 포맷 지원을 확인하고, 지원되지 않으면 기존 화면 또는 명시적 미지원 상태를 사용한다.

## 비동기 작업과 장애 처리

job 상태는 캐릭터 활성 상태와 구분한다. 제안 상태는 다음과 같다.

```text
QUEUED → RUNNING → VALIDATING → READY
             ├→ RETRY_WAIT → QUEUED
             ├→ RECONCILING → VALIDATING / RETRY_WAIT / FAILED
             └→ FAILED
QUEUED / RUNNING / RETRY_WAIT / RECONCILING / VALIDATING → CANCELLED
완료 전 작업 기한 초과 → EXPIRED
READY → 후보 선택 가능, 현재 캐릭터 전환·음성 실행 없음
모든 상태 → 철회·삭제 시 공개 금지, 삭제 작업으로 정리
```

READY는 필요한 자산·포맷·음성 레시피·품질 검사를 통과한 후보가 있다는 뜻이다. 가짜 worker의 READY는 합성 검사 통과로 표시하며 실제 시각·청취 품질 승인을 대신하지 않는다. 실패·취소·만료 뒤 같은 generationId를 재전송하면 기존 종료 상태를 반환한다. HTTP 재시도가 새 생성을 뜻하지 않는다.

worker는 짧은 DB 트랜잭션으로 작업을 점유하고 lease와 attempt fence를 증가시킨다. 네트워크·모델 작업 동안 DB 쓰기 잠금을 잡지 않는다. 후보 확정 시 현재 lease/fence·동의 epoch·삭제 표시를 다시 검사하는 조건부 갱신으로 늦은 worker의 결과를 버린다. 새 프로세스는 만료된 lease를 복구한다.

외부 호출에는 지원되는 경우 같은 provider idempotency key를 전달한다. 응답이 유실돼 실행 여부가 불명확하면 RECONCILING으로 두고 provider 작업 조회로 확인한다. 조회·멱등 기능이 없으면 자동 중복 제출을 멈추고 로컬 후보로 진행한다. 외부 side effect와 SQLite 트랜잭션은 원자적이지 않으므로 정확히 한 번 실행됐다고 기록하지 않는다.

재시도 가능한 연결 실패·429·5xx는 실행 여부가 확인된 경우에만 제한 횟수·기한·backoff와 jitter, Retry-After를 적용한다. 인증·계약·검수 실패는 무한 재시도하지 않는다. 개별 작업 비용·시간·파일 크기·전체 보관량 한도는 provider 도입 전에 설정하고, 수치와 실제 측정은 이번 문서에서 확정하지 않는다.

자산은 비공개 임시 경로에 기록하고 전체 바이트·digest·manifest 검증을 끝낸 뒤 DB에서 공개 가능 상태로 확정한다. 파일은 생겼으나 DB commit이 실패한 경우 고아 파일 정리 대상이다. DB에 READY를 먼저 기록하고 파일이 나중에 도착하도록 만들지 않는다. 실패한 출력은 선택할 수 없다.

생성 제출 ACK의 처리는 Python DemoOutbox의 단순 2xx 삭제보다 넓다. 앱은 응답의 generationId를 확인하고 job 추적 행을 저장하는 것과 제출 outbox 제거를 한 트랜잭션에서 수행해야 한다. 그 뒤 앱 재시작에도 상태 조회를 이어간다. 생성 완료 ACK를 받을 때까지 같은 제출을 무한 전송하는 방식은 사용하지 않는다.

## 자산 출처·복원·음성 경계

provenance는 결과가 만들어진 과정을 식별하는 자료이며 실제 도로의 Evidence와 별개다. 다음 항목을 결과 manifest와 연결한다.

| 자료 | 남길 값·한계 |
| --- | --- |
| 생성 출처 | LOCAL_CATALOG, MOCK_WORKER, REMOTE_MODEL 등 실제 실행 유형, recipe·template·model/checkpoint·tool 버전, seed, 생성 시각 |
| 입력 귀속 | 소유자 범위의 최소 의미 태그와 정규화 요청 digest. 원본 주소·GPS·목적지 문자열의 해시를 대신 저장하지 않음 |
| 자산 원천 | 입력 자산 ID·digest·출처와 사용 범위를 검토한 기록의 참조. 확인되지 않은 외부 이미지·음성 원천은 활성 catalog에 넣지 않음 |
| 변환 이력 | 입력과 출력 파일 digest, layer/rig 변환기 버전, 렌더러 호환 범위, 실패·품질 검토 결과 |
| 결과 보존 | 선택된 실제 파일·manifest·voice recipe의 불변 버전. 모델을 다시 불러 복원하는 방법에 의존하지 않음 |
| 실행 진단 | 내부 job·attempt·오류 분류·소요 시간. 토큰·provider 자격 증명·원문 프롬프트를 로그나 공개 manifest에 넣지 않음 |

provider 요청 ID와 상세 생성 설정은 내부 자료다. 클라이언트에는 복원에 필요한 최소 manifest만 제공한다. bytes는 SQLite JSON 본문이나 기존 256 KiB API에 base64로 넣지 않는다. 첫 합성 실험은 내장 catalog를 참조한다. 이후 파일 저장은 비공개 asset store와 인증된 다운로드 adapter로 분리하고 저장 backend 선택은 미확정으로 둔다.

다운로드 전에 소유권을 확인하고, 앱은 파일 크기·MIME·digest·renderer/rig 호환을 검증한 뒤 임시 캐시에서 활성 캐시로 원자적으로 옮긴다. HTML·스크립트·모델 출력 코드나 임의 URL은 실행하지 않는다. 원격 이미지 한 장이 있어도 2.5D layer·rig·표정이 자동 완성됐다고 보지 않는다.

음성은 희망 `VoiceRecipe`와 실제 적용 `VoiceBinding`을 나눈다. Binding에는 recipe 버전, provider capability 버전, 승인된 speaker/profile, 적용·무시된 controls, fallback 여부를 TTS가 기록한다. SERVER는 해당 참조를 보존하며 화자 선택·SDK 호출·발화 허가는 TTS가 소유한다.

현재 Pleos 어댑터로는 캐릭터별 고유 음색을 완료할 수 없다. 검증된 복수 화자나 제작 음성 후보가 준비되기 전에는 캐릭터 성격 메타데이터만 달라졌다고 보고한다. fallback으로 기존 ON_DEVICE 음성을 쓰면 원래 개별 음성의 구현으로 계산하지 않는다. fallback 허용·무음 선택·provider 실패 정책은 TTS 제안과 통합해 정하고, 세션 도중 예고 없이 목소리를 교체하지 않는다.

향후 생성 오디오를 도입하더라도 저장 파일은 재생 명령이 아니다. 앱이 text digest·recipe·locale·provider 버전에 맞는 승인 자산을 선택하고 현재 TTL·차량·포커스 정책을 다시 적용한다. TripReport를 발화할 경우 finalText를 성격에 맞게 다시 쓰지 않는다. 실제 오디오 캐시는 저장·재사용 조건과 청취 검증을 마친 뒤 추가한다.

## 컬렉션·동의·삭제·보관 수명

현재 서버의 30일 주행 보존과 장기 소장 목적은 다르다. 컬렉션은 별도 동의를 받은 선택 결과만 보관한다. 첫 구현은 로컬 컬렉션을 기본으로 하고 클라우드 동기화는 선택 기능으로 둔다. 온라인 수집을 위해 모든 주행 기록의 보존기간을 늘리지 않는다.

제안 저장 모델은 generation_jobs, candidates, characters, asset_refs, collection_entries, consent_grants, deletion_jobs/tombstones다. 모든 개인 자료는 owner를 포함한 키와 참조를 사용한다. characters와 collection_entries를 trips의 cascade 하위에 두지 않고, 별도로 동의받은 최소 기억만 저장한다. 주행 만료 후에도 보관 가능한 자료와 제거해야 할 연결을 정책으로 구분한다.

| 행동 | 제안 처리 |
| --- | --- |
| 원격 생성 미동의 | 의미 태그도 원격으로 보내지 않음. 로컬 생성·표시·수집은 계속 가능 |
| REMOTE_GENERATION 철회 | 신규 제출·재시도 중지, 실행 중 작업의 결과 공개 금지, 미선택 후보·생성 입력 삭제. 이미 별도 COLLECTION_SYNC로 저장한 최소 선택 결과는 그 동의로 관리 |
| COLLECTION_SYNC 철회 | 클라우드 카드·개인 자산 삭제 및 전송 중지. 로컬 보존 여부는 사용자에게 별도 선택으로 보여 주며 클라우드 철회가 로컬 전체 삭제를 뜻한다고 추정하지 않음 |
| 30일 주행 만료 | 주행·이벤트·원본 report·추적 가능한 trip 연결 제거. 따로 저장한 캐릭터·허용 기억 태그만 컬렉션 보관 정책에 따라 유지 |
| 사용자가 여정과 관련 자료 삭제 | 기본은 연결된 캐릭터·카드·job·개인 자산까지 제거. 캐릭터만 남기기는 별도 명시 선택과 비위치 기억만으로 구성한 독립 snapshot 필요 |
| 캐릭터 삭제 | 카드·선택·개인 파일·후보·작업을 비공개 처리하고 GC. 공유 내장 catalog 원본은 삭제하지 않음 |

기존 v1 DELETE는 새 도메인을 모르므로 전체 삭제를 해결한다고 주장하지 않는다. 향후 v2 통합 삭제 경계가 먼저 여정의 생성·업로드를 막고 관련 자료와 기존 trip 삭제를 조율해야 한다. 새 기능 대상 여정에는 server tombstone 또는 폐기된 동의 epoch 검사를 적용해 오래된 v1 업로드도 재생성하지 못하게 해야 한다. 이 동작은 호환 검토·회귀 검사 후 구현할 사항이며 이번에 바꾸지 않았다.

동의 철회 때 앱은 전송 대상 outbox·실행 예정 작업을 중단하고 삭제 요청은 별도 durable queue에 남긴다. 서버는 삭제 요청 수락 시 즉시 조회·다운로드·READY 확정을 막는다. provider 작업 종료·자산 GC·백업 반영은 별도 삭제 상태로 추적한다. 외부 provider가 삭제를 확인하지 않았다면 완료로 표시하지 않는다.

삭제 후 재등장을 막는 tombstone에는 원문 payload를 보존하지 않는다. 소유자 범위 ID와 폐기 epoch 등 최소 정보만 사용한다. tombstone 수명은 오프라인 재시도 유효기간보다 길어야 하며 기간을 확정하기 전에는 임의로 제거하지 않는다. 백업을 복원해도 삭제 표식을 먼저 적용하고, 새 로그인·토큰 체계가 없다는 현재 운영 차단도 유지한다.

초기 정책 제안은 미선택 후보·입력을 작업 유효기간 뒤 정리하고, 선택 컬렉션은 사용자가 삭제하거나 명시한 보관 정책이 끝날 때까지 보존하는 것이다. 구체적 기한·용량·백업 삭제 기한은 기능 활성화 전 정해야 한다. 독립 DB 테이블 추가 시 현재 `user_version=1`에서의 명시적 migration과 복구 절차가 필요하며 CREATE TABLE만 더하는 것으로 끝내지 않는다.

의미 태그도 개인의 목적을 드러낼 수 있다. 첫 단계는 합성 입력과 검수된 넓은 category만 사용한다. 병원·종교·개인 일정처럼 민감한 방문 목적을 위치 원문의 대체재로 자동 추출하지 않는다. 나중에 사용자가 목적지 사진을 제공하는 기능은 별도 입력 동의·메타데이터 제거·저장 수명 설계 대상으로 남긴다.

## 소유권과 첫 구현 단계

| 담당 | 제안 소유 범위 |
| --- | --- |
| PM·공통 앱 host | 출발 전 선택·주행 고정·도착 후 수집 UX, 로컬 DB·worker 연결 배정, 하나의 차량 정책 feed, 수용 기준 |
| AVATAR | 다형 identity, 2.5D 자산·rig·renderer 호환, 레시피·novelty·시각 검수, 캐릭터 복원·감정 journal 연결 |
| TTS | 캐릭터 voice recipe·승인 후보·capability·fallback, 실제 음성 적용·청취·재생 정책 |
| SERVER | 생성 job 멱등성·상태·저장, 자산 출처·권한·삭제, 컬렉션 계약, 동의·retention·동기화 검사 |
| 외부 점수 담당 | 검증된 이벤트·평가·최종 코멘트 생성. 캐릭터 생성이 평가 의미를 정하지 않음. 협의는 보류 |

SERVER 후보 모듈은 계약의 `character_models`, 작업 상태를 소유하는 `generation_jobs`, 불변 manifest·권한을 다루는 `assets`, 컬렉션·동의를 다루는 `collection`이다. 이름은 구현 전 조정할 수 있다. HTTP와 provider adapter는 이 규칙을 호출하고, 도메인 로직이 SDK·HTTP client를 직접 호출하지 않게 한다. 별도 서비스 경계는 필요가 확인될 때 분리한다.

첫 구현 제안은 합성 여정으로 동작하는 로컬 선택·가짜 원격 worker의 한 흐름이다. PM의 착수 배정 후 다음 순서로 진행한다.

1. AVATAR/TTS 제안의 characterId·recipe·manifest·voiceBinding 경계를 내부에서 맞춘다. 외부 payload를 요구하지 않는다. 전역 고정 identity 가정은 새 경로의 설계에서 제거하되 v1 결과와 기존 회귀 검사는 보존한다.
2. 새 초안 계약과 mock job 상태 전이를 별도 파일에서 만든다. 선택·재시도·철회·출발 후 완료 시나리오를 먼저 고정한다. 새 모델 호출 없이 복원 가능한 검수 catalog로 검증한다.
3. PM이 지정한 Android 저장 소유자가 앱의 ID·선택·inbox/outbox를 원자적으로 연결한다. SERVER의 Python 예제만 통과한 상태를 이 단계 완료로 표시하지 않는다.
4. 사용자 평가로 실루엣·재질·성격·목소리 조합의 귀여움·개별성·소장 의향을 비교한다. 성능·자산 호환과 함께 통과한 뒤 외부 모델·음성 provider의 비교 실험 범위를 별도로 정한다.

첫 흐름에서는 전 세계 고유 캐릭터 보장, 거래·공개 공유, 희귀도 경제, 다중 장치 동시 편집, 임의 재추첨을 추가하지 않는다. 방문 횟수·과속·장거리·위험 사건을 희귀도 보상으로 사용하지 않는다. 현재 novelty 0의 의미를 운전 점수나 성장 수치로 전용하지 않는다.

## 검증 기준과 현재 차단

아래는 향후 구현의 수용 기준이며 이번에 새로 실행한 테스트가 아니다.

| 시나리오 | 통과 증거 |
| --- | --- |
| 같은 경로의 두 새 여정 | 서로 다른 trip·character·generation ID. 실루엣·재질·성격 차이는 AVATAR 평가로 확인하며 ID 차이만으로 통과하지 않음 |
| 동일 요청 100회·동시 제출·ACK 유실 | job·선택·컬렉션 각각 하나, 원래 seed·payload·버전 유지. 내용 변경 재전송은 409 |
| 앱·worker 중단과 lease 회수 | 새 프로세스가 같은 작업을 복구. 이전 worker 완료가 fence 검사에서 거부되고 활성 캐릭터가 바뀌지 않음 |
| provider 수락 후 응답 유실 | RECONCILING에서 조회·보류. 지원 없는 provider에 맹목적으로 새 호출을 하지 않음 |
| reroute·앱 재시작·출발 후 늦은 READY | route revision은 갱신해도 characterId·선택 외형·voice binding 유지. UI 자동 교체·재발화 0회 |
| 오프라인·생성 실패 | 로컬 후보로 출발 가능. 실패한 job이 로컬 감정·차량 정책 처리를 막지 않음 |
| 창작 태그와 사실의 분리 | WATERFRONT/REST 입력만으로 VERIFIED 도로·DrivingEvent·점수 생성 0건 |
| 자산 손상·부분 다운로드·미지원 rig | 활성화 거부, 기존 선택 보존. digest·실제 렌더러 검사를 통과한 묶음만 적용 |
| 캐릭터 음성 | 요청 recipe와 실제 적용 controls·fallback 로그 대조, 캐릭터별 실제 청취 비교. 현재 Pleos 기본 음성만으로 고유 음색 완료 처리 금지 |
| 소유자 분리 | 다른 principal이 job·manifest·asset·collection을 조회·선택·취소·삭제할 수 없음 |
| 철회·삭제와 완료의 경합 | 즉시 비공개, 늦은 완료·재시도·백업 복원 후 부활 0건. 외부 삭제 미확인은 pending으로 남음 |
| 보관 수명·원문 보존 | 주행 만료 뒤 동의한 컬렉션 최소 자료만 남음. overallScore null, finalText 원문 유지 |
| v1 회귀 | 기존 서버91·schema drift·새 Kotlin JSON/API·TTS fixture 검사 유지. 새 계약 JSON을 v1에 잘못 보내면 명시적으로 거부 |

서버 복원 자체에는 남은 차단이 없다. [보존된 SERVER 보고](../../handoff/restoration/2026-11-02/server.md)와 실제 pytest·Ruff·HTTP 로그에서 Python 3.12.14, uv 0.9.7, 서버91 통과, 패키징, 새 Kotlin JSON10/API4쌍 결과를 읽어 확인했다. 이번 설계 조사에서 이 검사를 다시 실행하지는 않았다.

[PM의 최신 취합](/Users/pig30nidae/NUNTI/docs/handoff/restoration/2026-11-02/PM.md)은 새 환경의 P→D→P와 TTS 거부·취소 성공을 기록한다. 과거 Virtual Console inactive를 현재 미해소 차단으로 반복하지 않는다. 새 오디오 청취·가청 지연, 실제 내비·점수·Android HTTP를 연결한 제품 E2E는 여전히 별도 미검증이다.

새 기능의 실제 차단은 Android 영속 저장·동기화 부재, 다형 2.5D 자산과 renderer·품질 기준 부재, 실제 캐릭터별 음색의 미검증, 생성 job·컬렉션·동의·삭제·DB migration 미구현이다. 이들은 내부 합성 설계와 가짜 worker의 첫 구현을 막지는 않는다. 외부 payload·담당·일정 확보는 현재 작업의 선행 조건으로 두지 않는다.

이번 산출물은 이 proposal 한 파일이다. 문서 내 로컬 링크 21개와 JSON 예시 1개를 검사했고 모두 유효했다. tracked 파일의 HEAD 대비 변경은 없고 기존 미추적 복원 증거·도구도 보존했다. 사실 근거는 위 소스와 기존 실행 로그이며, 새 endpoint·테이블·provider 지원과 테스트 통과를 구현 사실로 주장하지 않는다.
