# 여정별 수집형 2.5D 캐릭터 제안

2026-11-02, Asia/Seoul. AVATAR 설계 보고. 기준 소스는 `ebde9027f97f56f80bf8262c1200dbbb92827483`, 작업 폴더는 `/Users/pig30nidae/NUNTI/.worktrees/avatar`, 브랜치는 `codex/avatar-next`다. 이 문서만 새로 작성했다. 아래 새 타입·수치·수용 기준은 구현 또는 합의가 끝난 계약이 아니라 AVATAR의 제안이다.

최신 요구는 PM 루트의 [여정별 캐릭터 브리프](/Users/pig30nidae/NUNTI/docs/product/journey-character-brief.md)다. 기존의 전역 고정 얼굴·몸체·음성을 **공통 세계관 + 캐릭터별 고정 정체성**으로 바꾸는 방향을 제안한다. 새 여정마다 실루엣·얼굴 비례·재질·성격이 다른 캐릭터를 만들고, 태어난 캐릭터는 재시도·reroute·재시작 뒤에도 같은 모습과 음성 recipe를 유지한다. 의상이나 색만 바뀐 결과를 새 캐릭터 품질의 성공으로 세지 않는다.

첫 구현 후보는 **여러 체형의 검수된 2.5D 파츠를 로컬에서 조합하는 방식**이다. 고정 카메라로 제작한 입체감 있는 몸체·재질 이미지와 표정·동작 rig를 사용한다. 온라인 생성은 후속 비교 대상으로 둔다. 외부 payload·공급자·담당 협의는 보류하며 합성 여정과 의미 태그로 먼저 검증할 수 있다.

추가 확정: 사용자는 **C · 반투명 기념 오브젝트**를 아트 방향으로 선택했다. 각 여정의 기억을 형태와 내부 무늬·빛에 담는 같은 세계관을 유지한다. 아래 구현 대안 R1~R3는 이 아트 방향을 구현하는 방법의 비교이며, 세계관을 다시 고르는 선택지가 아니다.

## 기존 구현에서 확인한 사실

| 근거 파일·심벌 | 현재 동작 | 새 요구에 대한 판단 |
| --- | --- | --- |
| [기술 선택 기록](../../../android/feature/avatar/reports/technical-review.md), [기존 담당 보고](../../handoff/reports/avatar.md) | 같은 캐릭터의 Journey Layer만 변경. 생성 타당성·재현성을 우선해 규칙 엔진과 2D 파츠를 선택했다 | 고정 identity와 생성형 이미지 제외는 과거 제품·구현 선택이다. 차량 플랫폼이 한 몸체만 허용한다는 근거는 없다 |
| [Assets.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/Assets.kt)의 `IdentityLayer`, `AssetManifest` | manifest당 identity 하나, 고정 face·silhouette·signature·persona·voiceProfileId | 새 체형·얼굴은 이름 필드 변경만으로 생기지 않는다. 캐릭터 recipe와 rig family로 분리할 필요가 있다 |
| [AvatarEngine.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/AvatarEngine.kt)의 `generate` | 다른 baseCharacterId 거부. 다섯 테마 후보를 평가하고 seed는 정확한 동점에만 사용. avatarId는 `baseCharacterId|routeId`의 digest | 같은 경로의 다른 여정을 구분할 생성 단위가 없다. routeId가 바뀌는 reroute에서는 ID도 바뀔 수 있어 새 요구와 다르다 |
| 같은 파일의 초기화·후보 점수 | 이력 입력이 없어 `score.diversity == 0`을 강제한다 | 이력을 명시적으로 입력받는 새 생성기에서는 창작 다양성을 평가할 수 있다. 기존 도로 근거 점수에 임의 가산점을 넣지 않는다 |
| [Rendering.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/Rendering.kt)의 `PlaceholderIdentity`, `Primitive`, `CharacterRenderer` | 320×320 고정 좌표의 몸체·얼굴. ellipse·rect·line·polyline만 사용. provider와 spec identity/digest를 대조한다 | 현재는 2D placeholder다. 텍스처·마스크·깊이 레이어·체형별 앵커·동작을 지원하는 2.5D renderer는 없다 |
| [Assets.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/Assets.kt)의 `ConstraintValidator` | 얼굴 보호 사각형과 외곽 범위, 허용 앵커·shape가 고정이다 | 여러 체형에는 rig별 보호 영역과 부착 제약이 필요하다. provider만 교체하면 모두 해결된다는 설명은 부정확하다 |
| [RouteFeatures.kt](../../../android/feature/navigation/src/main/kotlin/ai/nunti/navigation/RouteFeatures.kt), [WireAdapter.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/WireAdapter.kt) | routeId·revision·특징값에 맞는 근거와 신뢰 producer를 검사. 미확인은 UNKNOWN. production Mock 기본 불허 | 실제 사실의 경계로 재사용한다. 창작 태그를 이 경로에 주입하지 않는다 |
| [EmotionMachine.kt](../../../android/feature/emotion/src/main/kotlin/ai/nunti/emotion/EmotionMachine.kt) | 검증 이벤트·시간·중복·incident·현재 cause 회복을 처리하는 순수 reducer. 점수나 성격을 입력받지 않는다 | 감정 원인 판정은 유지한다. 성격은 같은 감정을 표현하는 모양과 말투에만 영향을 준다 |
| [WireAdapter.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/WireAdapter.kt)의 `AvatarReplay`, [EmotionReplay.kt](../../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/EmotionReplay.kt) | 원래 평가 시각·seed·rule/asset digest로 재생. journal은 수신 시각·이벤트·tick을 복원한다 | 보존 원칙은 재사용한다. 새 캐릭터·다중 rig·수집 이력·외부 생성 파일의 저장 형식은 추가 설계가 필요하다 |
| [MainActivity.kt](../../../android/app/src/main/kotlin/ai/nunti/app/MainActivity.kt) | Mock 경로 index와 seed만 SharedPreferences에 보관. Automotive에서는 production 연결 전 빈 화면 | 영속 컬렉션·실제 inbox/outbox·운영 host는 없다 |
| [AvatarVoiceBridge.kt](../../../android/app/src/voiceIntegration/kotlin/ai/nunti/app/AvatarVoiceBridge.kt) | avatarId·baseCharacterId·voiceProfileId와 감정을 TTS DTO로 투영한다 | 전달 경계는 있으나 캐릭터마다 실제 음색이 바뀐다는 증거는 아니다. 지원 제어·음성 후보 검증은 TTS 소유다 |

복원 상태는 [PM의 새 검증 취합](/Users/pig30nidae/NUNTI/docs/handoff/restoration/2026-11-02/PM.md)을 따른다. 기존 JVM 58개·합성 1,000개와 Kotlin JSON 10개/API 4쌍이 새 로컬에서 통과했고, 공식 Pleos 에뮬레이터의 P→D·속도 변화→P에서 화면 차단·복귀와 발화 거부·취소를 확인했다. 이번 설계 작업에서 다시 실행한 검사는 아니다. 경로·감정은 Mock이며 실차·production host·새 PCM 청취·내부 접근성 subtree 검증으로 확대하지 않는다. 과거 Virtual Console 503을 현재의 미해결 차단으로 다시 적지 않는다.

## 바꿀 제품 선택과 유지할 경계

| 구분 | 새 설계의 처리 |
| --- | --- |
| 변경할 제품 선택 | 전역 동일 몸체·얼굴·색·성격·음성, route 기반 ID, 의상 중심 후보, 이력 없는 다양성 0. 새 생성기에서 여정·캐릭터·컬렉션을 명시적으로 모델링한다 |
| 유지할 사실 검증 | 목적지명·방문 목적·분위기로 도로 비율·해안 통과·위험 사건을 추정하지 않는다. 근거 없는 실제 사실은 UNKNOWN이다 |
| 유지할 표시·발화 경계 | 플랫폼 허가 누락·차단·노후 시 화면과 접근성 설명을 숨긴다. 현재 주행 중 기본 차단을 유지한다. 명시적 정적 표시 허가가 생겨도 중립·고정 외형·무조작이며, 새 렌더링 방식이 허가를 열지 않는다 |
| 유지할 운영 경계 | host CarUx listener 하나 공유, production Mock 불허, 네트워크·동기화 동의와 독립적인 로컬 반응, 복원·서버 재전송으로 TTS 자동 재생 금지 |
| 유지할 기록 경계 | 원래 평가 시각·입력 출처·rule/asset digest 보존, 재부팅 전 monotonic 시계 원점 재사용 금지, 외부 점수·최종 코멘트의 소유권 유지 |
| 새 경험의 제한 | 위험 운전·속도·거리·운전 횟수에 희귀 보상을 걸지 않는다. 캐릭터 파괴·벌점·죄책감·연속 방문 압박을 사용하지 않는다. 도착 후 추억과 검증된 긍정 피드백을 다룬다 |

`RenderPolicy`는 주차에서도 현재 `animationsAllowed=false`다. 아래 미세 동작은 후속 주차 화면 설계안이다. 이미 허용된 동작으로 취급하지 않으며 PM의 host 범위 결정과 실제 정책 검증을 거쳐야 한다.

## 사용 흐름과 상태 소유

호스트의 사용 형태는 다음 정도로 제한한다. 이름은 제안이며 wire API가 아니다.

```text
reservation = journeys.reserve(startCommandId, journeyId, inspiration, verifiedFacts)
draft = characters.prepare(reservation, catalog, collectionSnapshot)
chosen = characters.choose(reservation.id, draft.candidateId)
character = journeys.seal(reservation.id, chosen, expectedVersion)
view = characters.present(character, emotionSnapshot, renderDecision)
```

`reserve`는 같은 출발 명령의 재시도에서 같은 reservation을 반환한다. `prepare`는 네트워크와 무관한 순수 결정 로직이며 후보와 탈락 이유를 만든다. `seal`의 영속화·중복 처리는 host 저장 경계 하나가 소유한다. renderer는 차량 상태나 서버 응답으로 새 캐릭터를 만들지 않는다.

| 단계 | 화면·행동 제안 | 저장·실패 처리 |
| --- | --- | --- |
| 출발 전 | 입력한 방문 목적과 분위기로 최대 3개 후보를 제시. 선택을 건너뛸 수 있고 각 후보의 모티브 출처를 짧게 설명한다 | 입력 snapshot·ID·seed를 먼저 예약한다. 출발 시 미선택이면 결정적인 기본 후보를 확정한다. 캐릭터 저장 실패로도 출발은 막지 않는다 |
| 이동 중 | 실제 정책이 허가하는 범위의 짧은 동행. 수집 조작·후보 교체·새 캐릭터 공개를 요구하지 않는다 | 캐릭터와 음성 recipe는 고정. route revision과 실제 감정 journal은 별도로 갱신한다 |
| 도착 후 | 캐릭터 카드와 사용자가 남긴 추억, 검증된 긍정 피드백을 보여 준다. 주차 확인 전에는 도착 신호만으로 UI를 열지 않는다 | 기존 characterId에 추억 기록을 추가한다. 종료 callback 반복으로 캐릭터나 보상을 중복 지급하지 않는다 |

생성 상태는 `Reserved → DraftReady → Sealed`로 둔다. 취소는 `Cancelled`라는 종료 상태다. 실패는 원인과 재시도 가능 여부를 가진 결과로 반환하며 `ready=true`와 누락된 자산을 함께 저장하지 않는다. `Sealed` 뒤의 자동 재생성·자동 교체는 금지한다. 출발 전 명시적으로 입력을 수정하면 같은 예약의 draft revision을 증가시키고 이전 계산 결과를 폐기한다. 확정된 캐릭터의 reroute는 이 입력 수정과 다르다.

저장에 실패하면 예약을 완료했다고 UI에 표시하지 않는다. 안전한 공통 대기 화면으로 이동할 수 있으며, 이미 영속화된 예약이 있으면 같은 ID로 재개한다. 영속화 전 프로세스가 종료된 경우 같은 캐릭터 복원을 보장한다고 주장하지 않는다.

## 사실과 창작 입력을 분리하는 타입

`JourneyId`, `GenerationId`, `CharacterId`, `CandidateId`, `RecipeDigest`는 서로 바꿔 쓸 수 없는 식별자로 다룬다. 다음 모델은 로컬 도메인 초안이다. SERVER wire 1.0의 새 DTO로 복제하거나 현재 schema에 필드를 끼워 넣지 않는다.

| 모델 | 필요한 내용과 규칙 | 소유 제안 |
| --- | --- | --- |
| `CreativeContext` | 허용 목록의 목적지 유형·방문 목적·사용자 선택 분위기. 각 태그에 USER_DECLARED 또는 SYNTHETIC 출처. 정밀 주소·GPS·목적지 원문을 자동 포함하지 않음 | host 입력 경계, AVATAR 모티브 규칙 |
| `VerifiedJourneyFacts` | 기존 extractor가 채택한 값·원본 route revision·평가 시각·audit. 미확인 필드도 명시 | navigation, producer 신뢰 등록은 host |
| `CollectionSnapshot` | 결정 시점의 로컬 컬렉션 revision, 비교 대상의 시각 descriptor, snapshot digest. 실제 이력 없음 상태와 빈 신규 컬렉션을 구별 | host 저장, AVATAR 비교 함수 |
| `GenerationReservation` | journeyId·generationId·예약 characterId·seed·입력 revision/digest·catalog/rule digest·이력 snapshot. 같은 예약에 다른 입력으로 재시도하면 명시적 충돌 또는 draft 수정 명령 | host의 단일 저장 경계 |
| `CharacterRecipe` | worldStyleVersion, rigFamilyId/version, body·face 비례, 재질/팔레트, 핵심 모티브, 이름, persona recipe, voiceRecipeRef, 자산 content digest | AVATAR, 음성 참조는 TTS와 합의 |
| `GenerationDecision` | 후보 전체, 제약 실패, 창작 출처, 사용한 사실, novelty 비교 결과, 선택 이유. 확정 recipe의 digest | AVATAR |
| `CharacterRecord` | Sealed recipe, 원본 생성 결정, 채택 자산 manifest·파일 해시, 도착 후 추억 기록 참조. 캐릭터 정체성과 추억을 별도 버전으로 관리 | 저장은 host/SERVER, 해석은 AVATAR |

두 입력 모델을 하나의 `tags` 목록으로 합치지 않는다. 예를 들어 사용자가 “바다 분위기로 독서하러 가요”를 고르면 물방울 모티브를 만들 수 있다. 설명은 “고른 바다 분위기에서 물방울 모양을 가져왔어요”다. 이것은 “실제 경로가 해안을 지나므로 물방울 캐릭터를 만들었어요”의 근거가 아니다. route facts는 여전히 UNKNOWN일 수 있다.

창작 출처가 전부 누락돼도 승인된 일반 모티브로 새 캐릭터를 만들 수 있다. 기존 실제 도로 특징의 fallback은 계속 UNKNOWN이다. 실제 운전 데이터가 없다는 이유로 캐릭터 다양성까지 없앨 필요는 없지만, 임의 창작을 검증된 사실로 표시하면 안 된다. 이름과 성격도 위험도·운전자 유형을 평가하는 문구로 생성하지 않는다.

## 렌더링 대안과 권고

아래는 소스에 비춰 본 구조 비교다. 외부 모델·상용 rig 도구의 현재 기능·가격·라이선스나 성능을 조사·검증한 표가 아니다. 전문 서비스 도입을 결정하거나 호출하지 않았다.

| 안 | 구조 스케치 | 품질·운영 장점 | 주요 비용과 한계 |
| --- | --- | --- | --- |
| R1. 검수된 여러 체형의 2.5D 조합, 첫 후보 | 의미 태그 → 로컬 recipe → 체형별 파츠/재질 atlas + 표정 rig → 레이어 renderer | 디자인 문법·얼굴·재현을 검수 가능한 범위로 묶고 오프라인에서도 완성 캐릭터를 제공할 수 있다 | 여러 몸체와 얼굴을 실제로 제작해야 한다. 조합 용량이 유한하며 단순 recolor로 흐르면 소장 가치가 낮다 |
| R2. 여정별 온라인 이미지 생성 + rig 정리 | 비식별 모티브 → 비동기 이미지 후보 → 분리·앵커·표정 검수 → 확정 자산 | 형상과 재질의 탐색 범위를 넓힐 수 있다는 가설 | 한 장의 좋은 이미지가 애니메이션 가능한 캐릭터를 보장하지 않는다. 투명 경계·표정 일치·부착 구조·응답 지연·비용·권리·실패 대체 검증이 추가된다 |
| R3. 여러 3D 기본 rig + 절차적 변형 | recipe → 메시·재질·얼굴 rig → 실시간 카메라·조명 | 여러 방향과 동작을 같은 모델에서 표현할 수 있는 구조 | 모델 제작, 관절 변형, 기기 GPU·열·배터리·렌더링 파이프라인 검증이 필요하다. 현재 Compose primitive 경로의 확장이 아니다 |

선택된 C 아트를 구현할 첫 후보로 R1을 제안한다. R2·R3와 비교하더라도 같은 반투명 세계관·합성 여정·표시 크기·표정을 사용한다. R1의 몸체를 3D로 제작해 고정 시점의 이미지로 굽는 제작 방식도 가능하다. 그 경우 런타임이 실시간 3D를 지원한다고 표시하지 않는다. 어느 구현 방식이 더 귀엽거나 소장 가치가 높은지는 아직 검증하지 않았다.

## 2.5D 디자인 문법과 rig 계약

공통으로 유지할 것은 부드러운 외곽, 읽기 쉬운 얼굴, 과도하게 번쩍이지 않는 재질, 일관된 카메라·광원·접지감이다. 모든 캐릭터의 눈 위치·몸통 모양을 같게 두지는 않는다. 첫 시안은 둥근 조약돌형, 세로 물방울형, 넓은 잎주머니형의 세 체형으로 비교한다. 종족·성격의 최종 명칭이나 사용자 선호는 아직 확정하지 않는다.

다음은 실물 생성 결과가 아닌 비교용 창작 스케치다. 전부 합성 태그이며 도로 정보는 UNKNOWN으로 둔다.

| 합성 입력 | 형태·재질 방향 | 성격·목소리 의도 | 보존할 개별성 |
| --- | --- | --- | --- |
| 책방 · 혼자 쉬기 · 포근함 | 낮고 둥근 반투명 조약돌 몸체, 우윳빛 투과감, 안쪽의 책장 같은 얇은 무늬 | 말수가 적고 다정함. 부드럽고 여유 있는 말하기를 희망 | 납작한 실루엣·작은 귀 비대칭·눈 비례. 내부 무늬를 빼도 구별 가능 |
| 전시 공간 · 새로운 것 보기 · 맑음 | 세로 반투명 물방울 몸체, 내부의 겹친 색면, 위쪽 작은 봉우리 | 호기심 있고 차분함. 또렷한 짧은 문장을 희망 | 세로 비례·봉우리·얼굴 배치. 색을 제거해도 첫 캐릭터와 다름 |
| 공원 · 함께 쉬기 · 산뜻함 | 넓은 반투명 잎주머니 몸체, 부드럽게 흐린 표면, 안쪽의 잎맥 같은 무늬 | 느긋하고 반가움을 잘 표현. 따뜻한 리듬을 희망 | 넓은 외곽·짧은 발 간격·볼 윤곽. 실제 식생·지형을 검증한 표현은 아님 |

음성 열은 희망 recipe다. TTS가 지원·청취 검증한 후보에 매핑할 수 있는지 확인해야 한다. 성격이 밝다는 이유로 실제 위험 이벤트의 표정을 기쁨으로 바꾸거나 발화 허가를 완화하지 않는다.

| 자산 요소 | 제안 계약·검수 항목 |
| --- | --- |
| 체형 rig | family별 정규화 좌표, pivot·anchor, 허용 변형 범위, face-safe mask, 외곽 mask, 앞/뒤 레이어 순서, 호환 part 목록. 서로 다른 family의 팔·얼굴을 무조건 혼합하지 않음 |
| 레이어 | 뒤쪽 장식 → 몸체 → 얼굴 바탕 → 앞쪽 파츠 → 표정 → 작은 하이라이트. 접지 그림자는 별도 레이어. 머리·팔이 겹치는 모든 허용 포즈에서 mask와 순서를 검수 |
| 재질·화질 | 고정 시점의 음영·접촉 그림자·하이라이트를 자산에 포함. sRGB와 alpha 처리 방식을 통일하고 밝은/어두운 배경에서 가장자리·번짐·마스크 틈을 검사. 텍스처 확대와 반투명 중첩도 확인 |
| 표현 | 각 family에 NEUTRAL·RELAXED·JOYFUL·STARTLED·CONCERNED·RELIEVED 6상태. 같은 캐릭터의 얼굴 비례·눈 기준점·외곽은 유지. 불안을 조롱하거나 벌주는 표현은 제외 |
| 동작 후보 | 주차 화면에서 짧은 눈깜박임·미세 호흡·고개 인사부터 비교. 과한 튀기·점멸·무한 반복 공개 연출은 제외. 첫 구현은 정적 6표정이며 lip sync·회전 관찰·자유 포즈는 후순위 |
| 품질 대체 | family별 검수된 중립 이미지와 썸네일 포함. 파츠 누락 시 임의 타 캐릭터로 바꾸지 않고 같은 캐릭터의 검증된 축약 표현을 사용. 그것도 없으면 자산 오류 상태로 표시 |

현재 `CharacterAssetProvider`의 `renderIdentity(emotion)`는 manifest의 단일 identity를 사용하고 출력도 단색 primitive에 묶여 있다. 새 renderer는 `sealed recipe + rig manifest + emotion + render decision`을 입력받도록 별도 실험 경계를 둬야 한다. 기존 v1 기록을 읽는 경로는 유지하되 새 캐릭터를 기존 `nunti-v1`이라고 위장하지 않는다. 공통 host와 Gradle의 실제 연결은 PM 배정 뒤 작업한다.

## 새 여정·재시도·경로 변경의 ID와 seed

| 상황 | 제안 결과 |
| --- | --- |
| 같은 목적지·같은 경로로 다시 출발 | 새로운 journeyId와 generationId, 예약 characterId를 발급. 이전과 같은 캐릭터를 재사용하지 않음. 새로운 외형인지는 별도 novelty·사용자 평가로 확인 |
| 생성 요청 재전송·버튼 중복·앱 재시작 | 같은 startCommandId/reservation을 읽고 같은 ID·seed·입력 snapshot·후보를 반환. 새 난수를 뽑지 않음 |
| 준비 중 사용자가 입력 수정 | 명시적 draft revision 변경으로 처리. 오래된 revision의 완료 응답은 후보나 확정 record를 덮어쓰지 못함 |
| 확정 뒤 reroute·routeId 변경·지연된 경로 도착 | 캐릭터·voiceRecipeRef 고정. route facts와 현재 정책만 별도로 갱신. 최초 창작 설명은 생성 당시 출처로 표시 |
| 확정 전 출발 | 로컬 후보 중 정해진 기본 후보를 원자적으로 확정. 늦게 온 온라인 후보는 자동 공개·교체·별도 수집 지급하지 않음 |
| 재부팅·재설치 후 동기화 | 저장된 record가 있으면 그대로 복원. 잃어버린 로컬 예약을 새 난수로 만들고 “동일 복원”이라고 부르지 않음 |

예약 ID는 경로·주소·목적지의 해시로 만들지 않는다. ID와 seed는 호스트가 예약 시 한 번 만들고 함께 저장한다. seed는 새 모델에서 256bit 값을 문자열로 보관하는 안을 제안한다. 현재 `Long` seed에 잘라 넣지 않는다. candidateId는 generationId와 candidate ordinal로 결정하고 확정 record에는 선택한 candidateId를 남긴다.

재현 계산은 버전이 붙은 canonical 입력, rule/catalog digest, 고정 이력 snapshot, seed, candidate ordinal을 사용한다. 문자열 Unicode 정규화, 키·집합 순서, 수치 단위를 정의하고 locale·플랫폼 기본 hash·불안정한 난수 순서를 사용하지 않는다. 후보 축별 난수는 명시적 domain label로 나눠 한 축 추가가 모든 기존 선택을 바꾸지 않게 한다. 계산 규격 자체에도 버전을 붙인다.

`seal`은 reservation 상태·draft revision·선택 candidate digest를 비교하는 조건부 저장이다. 동시에 두 후보가 확정되려 하면 한 결과만 채택하고 나머지는 기존 확정값을 읽는다. 여러 기기의 동일 여정 조율은 SERVER 초안과 합의할 항목이며 지금 전역 exactly-once를 보장하지 않는다.

## 컬렉션 novelty와 생성 설명

창작 후보의 제약 검증을 먼저 수행한다. 허용 체형·face-safe·파츠 호환·검수 자산·유효한 음성 참조가 없는 후보는 novelty가 높아도 제외한다. 그 뒤 모티브 적합성, 체형·얼굴·재질의 차이, 최근 반복 정도로 정렬한다. 점수는 캐릭터 선택 점수이며 운전 점수가 아니다.

첫 비교안은 최대 16개 내부 후보를 만들고, 로컬 최근 20개 캐릭터의 descriptor를 고정 snapshot으로 비교한다. 전체 소유 컬렉션의 동일 visualRecipeDigest도 확인해, 사용 가능한 다른 조합이 있는데 완전 중복을 고르는 일을 피한다. 이 수치는 속도·용량 실측 전의 실험값이다. 비교 대상 revision·선택 후보·각 탈락 이유를 보존한다.

descriptor는 silhouette family·몸체 비례·얼굴 비례·재질·핵심 모티브·팔레트로 구성한다. 이름·액세서리·색 차이만으로 “새로움 성공”을 통과시키지 않는다. 첫 품질 게이트는 최근 가장 비슷한 캐릭터와 비교해 적어도 하나의 구조 축과 다른 한 축이 달라지는 것이다. 실제 차이가 지각되는지는 실루엣·소장 의향 평가가 결정한다.

이력이 제공되지 않으면 `HISTORY_UNAVAILABLE`을 기록하고 novelty는 비활성화한다. 빈 신규 컬렉션은 비교 대상이 0개라는 별도 사실이다. 후보 공간을 소진하면 무한 재시도하지 않고 반복 가능성을 기록한다. 새 ID가 무한한 시각적 유일성을 뜻하지 않는다. 재생성·경로 우회·장거리 운전을 유도해 희귀 캐릭터를 얻도록 하지 않는다.

재시도 동안 컬렉션에 다른 캐릭터가 추가돼도 원래 예약의 snapshot으로 같은 결과를 유지한다. 다른 기기의 최근 기록을 아직 받지 못했다면 해당 범위의 중복 회피를 보장하지 않는다. 도착 후 성장은 별도 추억·관계 기록으로 누적하고 몸체나 목소리를 몰래 갈아끼우지 않는다.

## 저장·복원·음성 연결 경계

복원에는 **선택된 recipe와 실제 자산 파일**이 기준이다. 외부 생성기를 향후 사용하더라도 모델명·seed만 저장해 같은 이미지를 다시 만들 수 있다고 약속하지 않는다.

| 보존 대상 | 복원 원칙 |
| --- | --- |
| recipe와 결정 | 선택 후보와 전체 후보 평가, 입력 출처, 원래 사실 평가 시각, catalog/rule/generator 버전·digest, seed와 이력 snapshot. 새 시각·새 catalog로 묵시적 재추첨 금지 |
| 자산 bundle | 파일별 content digest, rig 버전·호환성, 해상도·색/alpha 규격, 제작 출처·권리 검토 상태. 파일 쓰기와 해시 검증이 끝난 뒤 manifest 참조를 원자적으로 확정 |
| 오류·부분 다운로드 | 완성되지 않은 bundle을 활성화하지 않음. 중립 썸네일도 같은 캐릭터인지 확인. 손상 파일을 새 캐릭터로 자동 대체하지 않고 재다운로드 또는 자산 오류로 처리 |
| emotion journal | characterId와 trip/session을 명시적으로 결합. 원래 수신 시각·tick·dedup·현재 cause를 복원. 재부팅에는 새 monotonic 시계와 세션 시간 연결이 필요. 추억 카드 열람은 reducer 입력이나 발화 재생을 유발하지 않음 |
| voice recipe | 캐릭터 확정 시 TTS의 검증된 recipe 참조를 함께 고정. 희망 성격과 실제 선택 voice/provider를 구별. 지원 불가·오프라인 대체는 TTS 정책을 따르고 다른 음성으로 대체됐음을 기록 |
| 삭제·동의 | 로컬 컬렉션과 클라우드 동기화 동의는 분리. 동의 없는 외부 생성 전송 금지. 삭제한 캐릭터가 오래된 생성 callback·복원·동기화로 부활하지 않도록 host/SERVER가 처리 |

비교 이력 snapshot에는 위치 원문을 넣지 않는다. 삭제 요청에 해당하는 유래 데이터·관련 snapshot도 삭제 또는 축소한다. 그 결과 생성 과정을 완전히 재실행할 근거가 사라졌다면 재현 가능 범위를 낮춰 기록한다. 삭제된 정보를 hash라는 이유로 숨겨 보존해 완전 재현을 약속하지 않는다. 남겨 두기로 한 캐릭터의 확정 recipe와 승인된 자산만으로 표시할 수 있는지 별도로 판단한다. 보존기간·자산 권리 만료 시 처리는 SERVER 초안과 후속 합의한다.

wire v1 `AvatarSpec`은 임의 ID 문자열을 받으므로 문자열 enum 자체가 여러 캐릭터를 막지는 않는다. 하지만 [schema](../../../contracts/v1/AvatarSpec.schema.json)의 `additionalProperties=false`와 [계약 의미 규칙](../../../contracts/v1/README.md), compact projection에는 새 generation job·rig·수집 이력·asset provenance를 표현할 자리가 없다. `baseCharacterId`나 `accessoryIds`에 새 bundle JSON을 숨겨 넣지 않는다. 로컬 실험 모델을 먼저 검증하고 SERVER가 별도 버전 또는 별도 계약을 제안하도록 한다. 기존 route revision·avatar 불변성 규칙의 호환성도 함께 검토해야 한다.

현재 `AvatarReplay`는 기본 AvatarEngine으로 재생하므로 새 모델의 복원기로 사용할 수 없다. legacy v1 기록은 기존 reader로 읽고, 새 record는 명시적인 별도 format discriminator로 나눈다. 과거 기록을 수집형 캐릭터로 자동 재생성하거나 기존 ID 의미를 소급 변경하지 않는다.

## 첫 구현 단계와 수용 기준 제안

이번 문서 이후 PM이 배정할 후보 단계다. 기존 app host·Gradle·wire 변경이나 외부 호출은 시작하지 않았다.

| 단계 | 범위·소유 제안 | 통과를 판단할 산출물 |
| --- | --- | --- |
| 1. 로컬 recipe 실험 | PM 생성 레시피 프로토타입과 모델 이름·입력 경계를 맞춘 뒤 AVATAR가 순수 후보 생성·rig 제약·novelty 비교를 담당. 외부 사실은 합성 fixture 또는 UNKNOWN | 6개 합성 여정 × 3후보의 recipe·이유·descriptor. 같은 경로의 새 여정과 중복 요청을 구별하는 자동 검사. 기존 engine의 사실 검증을 우회하지 않음 |
| 2. 정적 2.5D 자산·renderer | AVATAR가 승인된 세 family 자산·6표정·썸네일을 연결. 공통 host 연결 전에 독립 렌더링 결과로 비교 | 체형이 다른 18개 후보의 contact sheet, 단색 실루엣·소품 제거·작은 썸네일 비교, 밝은/어두운 배경·6표정 QA. 현재 flat placeholder를 완료 자산으로 재분류하지 않음 |
| 3. 예약·컬렉션 영속 경계 | PM이 host 소유자를 배정하고 SERVER가 원자성·동기화·삭제를 검토. AVATAR는 recipe/replay와 journal 결합을 검토 | 선택 직전/직후 강제 종료, 중복 완료, reroute, reboot, 자산 손상, 삭제 후 늦은 응답에서 동일 캐릭터 또는 명시적 실패. 출발·로컬 안전 정책이 저장이나 네트워크를 기다리지 않음 |
| 4. 캐릭터별 음성과 주차 동작 | TTS의 실제 지원·청취 결과를 받아 검증된 voice recipe와 연결. 동작은 PM의 주차 표시 범위 확정 뒤 추가 | 캐릭터를 가리고/보이고 같은 문장을 청취해 외형·성격과 음성의 적합성을 비교. 미지원 음향 제어를 성공으로 세지 않음. 표시 정책·lifecycle·자동 재생 금지 재검증 |

자동 검증에는 다음을 포함한다.

- 새 여정은 새 characterId를 갖고, 같은 예약의 반복·동시 요청·재시작은 같은 선택 recipe와 ID를 반환한다. 후보 선택 뒤 reroute와 새 routeId도 정체성을 바꾸지 않는다.
- 입력 순서·locale가 달라도 고정 입력·버전·이력 snapshot·seed의 recipe digest가 같다. 1,000개 합성 예약에서 재현·제약·기록 검사를 수행하되 이것을 사람의 소장 가치 점수로 쓰지 않는다.
- 사용자 “산책/바다 분위기” 태그를 바꿔도 검증된 도로·운전 사실이나 reducer 감정은 생기지 않는다. 실제 근거 삭제·만료 시 UNKNOWN이 유지된다.
- 기존 `identity fixed across routes and seeds`는 legacy 경로에서 유지한다. 새 경로에는 “한 캐릭터의 표정·복원·reroute 간 identity 고정”과 “여러 여정의 구조적 다양성” 검사를 별도로 둔다. 기존 테스트를 삭제해 통과 수만 맞추지 않는다.
- 정책 없음·차단·노후·백그라운드·Car 연결 해제에서 화면과 접근성 subtree를 실제 instrumentation으로 확인한다. 승인된 정적 표시 경로에는 외형 교체·동작·조작이 없다. 새 자산은 플랫폼 허가의 입력이 아니다.
- 각 family의 모든 허용 파츠·표정에서 얼굴 가림·외곽 잘림·레이어 관통·누락 anchor가 없다. 64px·128px 썸네일, 320dp 상세, 기존 1682×1210·847×910 창을 시작 표본으로 삼고 전체 기기 보장으로 쓰지 않는다.

렌더링 성능은 최종 자산으로 측정한다. 첫 실험 예산은 동작을 평가하는 60Hz 시험 환경에서 프레임 p95 16.7ms 이내, 단일 활성 캐릭터의 해제 전 decoded texture 32MiB 이내, 로컬 후보 준비 p95 200ms 이내다. 1024×1024 RGBA 한 장은 압축 전 약 4MiB이므로 원본 파일 용량만으로 메모리를 판단하지 않는다. 이 값들은 제품 SLA나 실측 결과가 아니며 대표 기기·실제 표시 크기로 조정한다. 초과하면 해상도·활성 레이어·동작을 줄이고 실패 로그를 남긴다. 정적 화면에서 지속적인 animation frame loop를 돌리지 않는다.

귀여움과 소장 가치는 사람의 평가가 필요하다. 첫 제안은 12명에게 무작위 순서의 합성 6여정·18후보를 보여 주는 탐색 평가다. 5점 척도 귀여움·소장 의향·여정 연관성, 자유 응답, 같은 경로의 다른 여정에서 구별되는 정도를 각각 수집한다. 이름·색·소품을 제거한 실루엣 비교도 따로 수행한다. “새 ID”나 “다른 hash”를 개별성 성공으로 세지 않는다.

초기 수용안은 귀여움 중앙값 4/5 이상, 참가자 12명 중 9명 이상이 소장하고 싶은 후보를 하나 이상 선택, 같은 캐릭터의 6표정 매칭 정확도 90% 이상, 다른 여정 캐릭터 구별 정확도 80% 이상이다. 이 수치는 PM이 평가 전 확정할 가설이다. 사람 수·문항 수·오답과 의견을 함께 보고하고 통계적 일반화나 운전습관 개선을 입증했다고 주장하지 않는다. 정적 시안이 이 기준을 못 채우면 조합 수 확대보다 체형·얼굴·재질을 먼저 수정한다.

## 현재 가능 범위와 남은 결정

지금 가능한 일은 기존 소스를 근거로 합성 여정 recipe와 세 체형의 비교 기준을 정하고, 구현 승인 뒤 순수 생성기·정적 renderer부터 검증하는 것이다. 실제 외부 feed가 없어도 이 단계는 진행할 수 있다.

아직 지원하지 않는 것은 여러 체형의 제작 완료 자산, 2.5D renderer·동작 rig, 여정별 예약·컬렉션 저장, 캐릭터별 실제 음향 차이의 검증, 실제 내비·GIS·DrivingEvent·production host 연결이다. 기존 58개 검사가 새 수집형 경험을 검증한 결과는 아니다.

PM이 다음으로 정할 항목은 C 아트 안에서의 투과감·얼굴 가독성·체형 수, 출발 전 후보 선택과 자동 확정 경험, 첫 자산 제작 범위, 공통 host 저장의 소유자, 위 품질 게이트다. TTS의 검증된 voice recipe와 SERVER의 생성·저장 초안은 내부 설계 단계에서 맞춘다. 실제 payload·외부 담당·전문 모델 도입·결제·배포 결정은 이번 보고의 선행 조건으로 요구하지 않는다.

## C 아트 선택에 따른 AVATAR 보완

반투명 기념 오브젝트를 기준으로 위 재질 예시를 갱신했다. 다른 세계관의 재선택이나 실시간 3D 도입을 뜻하지 않는다. 다음은 그 선택을 구현하기 위한 제안이며 자산 제작·렌더링 검증은 아직 수행하지 않았다.

- **형태와 귀여움.** 둥근 외곽·작은 팔다리·읽기 쉬운 얼굴로 동승자 인상을 유지한다. 같은 투명 용기의 내부 그림만 바꾸지 않고 체형·얼굴 비례도 구별한다. 거친 불투명 덩어리나 천 몸체를 섞어 컬렉션의 재질 문법을 흐리지 않는다.
- **내부 무늬와 빛.** 외피, 내부 기억 모티브, 얼굴, 제한된 하이라이트를 분리하고 깊이 순서를 rig에 고정한다. 첫 구현은 고정 카메라의 사전 제작 음영·투과 표현을 사용한다. 실시간 굴절이나 동적 광원을 지원한다고 주장하지 않는다. 내부 무늬의 모양·배치·광색도 recipe와 asset digest에 포함해 복원 때 다시 추첨하지 않는다.
- **가독성과 정책.** 얼굴 보호 영역에는 무늬·반사광이 눈과 입을 덮지 않게 하고 얼굴·윤곽의 대비를 확보한다. 밝은/어두운 배경, 작은 썸네일, 6표정에서 투명 경계·중첩·얼굴 식별을 검사한다. 빛은 첫 단계에서 정적 표현이며 점멸·움직이는 입자·주행 중 공개 효과를 넣지 않는다. 반투명 합성의 활성 레이어·메모리도 기존 성능 예산으로 측정한다.
- **기억과 사실.** 생성 때는 방문 의도에 따른 창작 모티브로 표시한다. 도착 뒤 사용자가 확인한 기억은 별도 버전의 카드·내부 기념 무늬로 보관하는 안을 제안한다. 주차 상태에서 명시적으로 채택하며 기존 캐릭터의 몸체·얼굴·음성을 바꾸지 않는다. 원본 recipe를 덮어쓰지 않고 되돌릴 수 있게 한다. GPS 원문을 그대로 무늬로 옮기거나 위험 운전으로 빛·희귀도를 보상하지 않는다.
- **담당 연결.** TTS에는 반투명 재질이라는 이유로 특정 음색·효과음을 강제하지 않고 캐릭터별 성격 recipe와 가독성 있는 표현 의도를 전달한다. SERVER에는 원본 캐릭터와 후속 기억 표현의 버전·자산 참조·삭제 범위를 구분하는 설계를 제안한다. 실제 공통 계약 변경은 이번 범위 밖이다.

다음 AVATAR 검토물은 PM이 만든 C 방향 시안에 대한 실루엣·얼굴·내부 무늬·레이어 분해 가능성 평가다. 외부 호출과 이미지 생성은 PM이 담당하고, AVATAR는 현재 제안서 외의 파일을 변경하지 않는다.
