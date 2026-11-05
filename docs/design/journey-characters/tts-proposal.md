# 여정별 수집형 캐릭터의 음성 설계 제안

2026-11-02, Asia/Seoul. TTS 담당의 읽기 조사와 설계 제안이다. 기준 HEAD는 `ebde9027f97f56f80bf8262c1200dbbb92827483`, branch는 `codex/tts-next`, 작업 폴더는 `/Users/pig30nidae/NUNTI/.worktrees/tts`다. 이번 작성에서 수정한 파일은 이 문서뿐이다. 기능 구현, 음성 합성 API 호출, 녹음, 결제, 자격 증명 요청은 하지 않았다.

최신 기준은 PM의 [여정 캐릭터 브리프](/Users/pig30nidae/NUNTI/docs/product/journey-character-brief.md)다. 권장 방향은 **검수한 한국어 음성 후보에서 캐릭터별 음성 레시피를 선택하고, 선택 결과를 캐릭터와 함께 보존하는 것**이다. 음성 레시피는 화자·리듬·표현의 조합이다. 출발 전에 같은 화자의 기본 문장을 준비하고, 새 문장은 같은 화자로 합성하는 방식을 비교 대상으로 삼는다. 현재 Pleos 기본 음성은 비교 기준으로 유지한다. 캐릭터별 음색이 구현됐다고 표시할 수 있는 상태는 아니다.

## 확정 아트 방향의 음성 보완

2026-11-02 PM 추가 전달에 따라 사용자가 선택한 아트 방향은 **C · 반투명 기념 오브젝트**다. 여정의 기억이 형태와 내부 무늬·빛에 남는 수집형 2.5D 캐릭터를 기준으로 한다. 아래의 공급 방식 A·B·C는 별도의 기술 비교이며, 아트 방향 선택으로 외부 TTS 도입까지 확정된 것은 아니다.

- 공통 음성 문법은 또렷한 한국어와 부드러운 발성으로 제안한다. 반투명 재질을 모두 높은 피치·속삭임·유리 울림으로 표현하지 않는다. 캐릭터별 개성은 검수한 화자와 리듬·문장 끝 표현에서 구별한다.
- AVATAR가 정한 형태·내부 무늬·빛의 창작용 특성을 recipe 선택에 함께 사용한다. 잔잔한 물결 무늬에는 안정된 리듬, 겹친 기억 무늬에는 호기심 있는 리듬을 비교할 수 있다. 이는 창작 대응안이며 도로·운전 사실의 증거가 아니다.
- 내부 빛의 애니메이션이나 무늬 갱신은 발화·효과음 트리거로 연결하지 않는다. 컬렉션에서 추억을 다시 보는 경우에도 실제 주차 상태의 새 사용자 요청과 기존 발화 정책을 따른다. 오래된 음성 요청을 복구하지 않는다.
- 캐릭터의 기억이 추가돼 내부 무늬·빛이 달라져도 확정 화자는 유지한다. 음성 recipe와 수집한 클립의 digest를 함께 보존한다. 이 방향을 표현하기 위한 잔향·효과음 제어는 현재 Pleos 지원 기능으로 선언하지 않는다.

첫 청취 비교는 PM이 준비한 같은 아트 방향의 세 캐릭터 시안과 기존 세 음성 특성을 조합한다. 외형 적합성·귀여움·소장 의향에 더해, 다시 만났을 때 같은 캐릭터로 느껴지는지 평가한다. 새 이미지·음원 생성은 이번 TTS 작업에 포함하지 않는다.

## 기존 사실과 변경할 제품 선택

| 구분 | 확인한 사실 또는 새 요구 | 설계에 미치는 영향 |
| --- | --- | --- |
| 과거 제품 선택 | [기존 TTS 보고](../../handoff/reports/tts.md)는 전역 `nunti-default-v1`과 같은 화자 유지를 정했다 | 새 요구에 따라 캐릭터별 프로필로 바꿀 수 있다. SDK의 강제 제약은 아니다 |
| 새 제품 요구 | 여정마다 외형·성격·목소리가 다른 캐릭터를 만들되 동일 생성 요청의 재시도, reroute, 재시작은 보존한다 | 음성 선택을 매 발화나 경로 revision마다 다시 하지 않는다 |
| 현재 구현 | [Models.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/Models.kt)는 프로필 목록과 `preferredVoiceId`를 표현한다. [VoiceProfiles.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/VoiceProfiles.kt)는 capability와 검증된 화자 목록을 검사한다 | 프로필 ID를 늘리는 것과 실제 다른 소리를 내는 것은 별도 작업이다 |
| 현재 구현의 공백 | `VoiceProfileManager.resolve`는 `baseSpeakingStyle`을 실제 제어에 쓰지 않는다. 감정은 `EmotionVoiceMapper`의 설명 문자열만 바꾼다. `AvatarVoiceInput.persona`와 `voiceStyleHint`도 음향 제어로 전달하지 않는다 | 메타데이터 변경을 캐릭터 음성 구현 완료로 판정하지 않는다 |
| 경계의 기존 선택 | [AvatarVoiceBridge.kt](../../../android/app/src/voiceIntegration/kotlin/ai/nunti/app/AvatarVoiceBridge.kt)는 `COMPANION`을 넣는다. [ContractBridge.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/ContractBridge.kt)의 `fromVoiceProfile`은 wire persona를 로컬 `VoiceProfile`에 보존하지 않는다 | 성격별 레시피는 별도 로컬 모델이 필요하다. 브리지 변경은 후속 PM 통합 범위다 |
| 유지할 정책 | 승인 텍스트와 `TripReport.finalText` 원문, 실제 차량·오디오·lifecycle 상태, TTL·중복·취소 정책 | 캐릭터의 희귀도·귀여움·생성 성공은 발화 허가가 아니다 |

`COMPANION`은 동승자라는 제품 역할로 남길 수 있다. 그 안의 차분함·호기심·장난기는 캐릭터별로 다르게 설계한다. [VoiceProfile wire 1.0](../../../contracts/v1/VoiceProfile.schema.json)은 persona를 `COMPANION` 단일 enum으로 제한하지 않는다. 다만 새 레시피 저장 구조나 provider 버전을 이 계약이 이미 지원한다고 해석하지 않는다.

다음 규칙은 새 공급 방식에도 그대로 적용한다.

- TTS가 점수·위험·최종 코멘트를 생성하거나 원문에 감탄사·캐릭터 이름을 덧붙이지 않는다. 캐릭터별 대사는 별도의 승인된 텍스트 입력이다.
- 창작 모티브는 발화 근거와 분리한다. `바다 느낌`, `휴식 목적`은 도로 검증이나 운전 이벤트가 아니다. 정밀 주소·GPS를 음성 생성 입력에 자동 포함하지 않는다.
- 실제 플랫폼 상태가 누락됐거나 오래됐으면 UNKNOWN을 유지한다. 포커스 성공만으로 재생하지 않는다. 호스트는 CarUx listener 하나를 공유한다.
- 취소·만료·실패·재접속·재시작 뒤 과거 발화를 자동 재생하지 않는다. suspend 뒤에는 새 session을 만든다. 자산 복원과 발화 큐 복원은 다르다.
- 현재 80 codepoint·15초 간격·60초 문구 반복·TTL 최대120초를 이번 설계에서 완화하지 않는다. 제품 초기 설정이며 OEM 규정 수치는 아니다.

정책의 실제 소스는 [SpeechPlaybackPolicy.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/SpeechPlaybackPolicy.kt), [SpeechQueueManager.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/SpeechQueueManager.kt), [AndroidVoiceSession.kt](../../../android/feature/voice/src/main/kotlin/ai/nunti/voice/AndroidVoiceSession.kt)다.

## Pleos에서 실제로 확인한 제어

이번 조사에서 로컬의 공식 AAR 3.3.1 SHA-256을 다시 확인했다. 값은 lock과 같은 `bfbfb58376c69604afad3389878980461971683f0c51f619d03ab74b5e6a0375`다. 추출된 JAR의 `TextToSpeech`, `EventListener`, `AmbientAi`를 `javap -public`으로 읽었다. 장치에서 새 메서드를 호출하지 않았다.

| 항목 | 바이너리와 소스에서 확인한 범위 | 현재 판정 |
| --- | --- | --- |
| 초기화·언어·시작·중지·해제 | `initialize`, `setLocale(Locale)`, `speak(String, boolean)`, `stop`, `release` | [AndroidPleosConnection.kt](../../../android/feature/voice/src/main/kotlin/ai/nunti/voice/AndroidPleosConnection.kt)에 연결돼 있다 |
| 출력 속성 | `setAudioAttributes`, `setAudioZoneId` | 전자는 기존 포커스와 동일 속성으로 사용한다. zone은 사용하지 않으며 음색 제어가 아니다 |
| 화자 | `setSpeakerType(String)`, `AmbientAi.setSpeaker(String)` 존재 | 허용 문자열·mode별 적용·한국어 음질 미검증. 현재 어댑터는 호출하지 않는다 |
| 속도·피치·감정·PCM·padding | 확인한 위 public API에 전용 메서드가 없다 | 이 버전에서 지원한다고 선언할 근거가 없다. SDK 전체의 영구적 불가능을 주장하지 않는다 |
| 저수준 context | `AmbientAi.updateEicContextInfo(String)` 존재 | 문자열의 의미·지원 규약 미확인. 감정 JSON을 임의 주입하는 경로로 사용하지 않는다 |
| 재생 콜백 | `onReady`, `onStart`, `onDone`, `onStop`, `onError`, RMS | PCM이나 requestId가 아니다. 현재 연결 세대별 늦은 콜백 격리를 유지한다 |
| mode | ON_DEVICE 기본, HYBRID·SERVER 등록 경로 구현 | 다른 공급자의 클라우드 합성을 Pleos `SERVER` mode로 표시하지 않는다 |

[PleosTtsProvider.kt](../../../android/feature/tts/src/main/kotlin/ai/nunti/tts/PleosTtsProvider.kt)의 `capabilities`에는 검증된 화자 ID가 없고 제어는 LOCALE뿐이다. `speak`는 non-null `speakerId`를 `UNVERIFIED_SPEAKER`로 거부한다. 현재 구현에서 승인된 선택 화자는 0개이며 실제 사용 경로는 플랫폼 기본 화자다.

공식 [API 목록](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/text-to-speech/ai.pleos.playground.tts/text-to-speech/entry)과 [setSpeakerType 페이지](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/text-to-speech/ai.pleos.playground.tts/text-to-speech/set-speaker-type)를 2026-11-02에 조회했다. 가져온 본문에는 허용 화자 값 설명이 없었다. 따라서 임의 문자열을 후보로 등록하지 않는다.

재확인 명령은 다음과 같다. `NUNTI_JAVAP`과 `NUNTI_TTS_JAR`은 현재 로컬 설치 위치이며 Git 필수 경로가 아니다.

```sh
NUNTI_JAVAP=/Users/pig30nidae/NUNTI/.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home/bin/javap
NUNTI_TTS_JAR=/Users/pig30nidae/NUNTI/.local/tts-tools/artifacts/pleos-tts.jar
"$NUNTI_JAVAP" -public -classpath "$NUNTI_TTS_JAR" \
  ai.pleos.playground.tts.TextToSpeech \
  ai.pleos.playground.tts.listener.EventListener \
  ai.pleos.playground.tts.api.AmbientAi
```

## 세 공급 방식의 비교

아래는 제안 비교이며 새 음질·가격·지연 측정값은 없다. 자체 모델 학습과 무제한 새 화자 생성은 첫 구현 범위에서 제외한다.

| 방식 | 구조 | 캐릭터 개별성 | 오프라인·실패 | 추가 작업과 판단 |
| --- | --- | --- | --- | --- |
| A. Pleos 직접 합성 | 승인 텍스트 → 기존 정책·큐 → Pleos | 현재는 모두 기본 화자. 문구만 달리해도 음색 차이를 충족하지 못한다 | ON_DEVICE 경로를 활용한다. 실제 무네트워크 검사는 별도다 | 가장 작은 변경. 비교 기준으로 유지하고, 화자 값이 검증되면 재평가 |
| B. 검수된 문장 음성 묶음 | 사전 녹음 또는 승인된 합성 파일 → 로컬 player → 같은 정책·포커스 | 소수 화자군과 연기별 클립을 안정적으로 제공한다 | 설치된 정확한 문장만 오프라인 재생 가능. 없는 문장을 클립 이어붙이기로 만들지 않는다 | 귀여움·소장 경험의 첫 청취 비교에 적합. 임의 `finalText` 낭독을 해결하지 못한다. 자산 제작·배포·권리 확인과 player 구현 필요 |
| C. 승인 화자 목록과 같은 화자의 사전 생성·동적 합성 | 의미 태그 → 저장된 레시피 → 기본 문장 파일, 새 승인 텍스트 → 동일 provider·화자 → player | 화자와 검수한 리듬·표현을 캐릭터에 고정한다. 유한 후보의 조합이며 모든 캐릭터의 음색이 유일하다고 보장하지 않는다 | 같은 레시피·같은 텍스트의 파일이 있으면 사용. 없고 합성이 불가능하면 음성 대기 또는 무음 | 목표 제품의 우선 검토안. 네트워크·보존 정책·provider 갱신·플레이어·비용 측정 필요. 도입 확정 아님 |

C를 우선 검토하는 이유는 캐릭터의 첫인사와 나중의 새 문장을 같은 화자로 묶을 수 있기 때문이다. B는 승인된 짧은 문장으로 먼저 매력을 평가하는 실험 범위로 사용할 수 있다. 외부 연결이 승인되기 전에는 합성 여정과 비실행 레시피만 만든다. A의 기본 음성을 C 캐릭터의 목소리로 조용히 대체하면 음성 정체성이 깨진다.

외부 후보의 문서 예로 Azure Speech의 한국어 `ko-KR-SunHiNeural`, `ko-KR-InJoonNeural`, `ko-KR-JiMinNeural`을 청취 후보에 둘 수 있다. 모두 제품 승인 전 후보다. 이름이나 성별 표기만으로 귀여움·연령감·성격을 배정하지 않는다. 공식 목록은 화자별 스타일이 다름을 보이며, 한국어 지원이 여섯 감정 지원을 뜻하지 않는다. [한국어 화자 목록](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)

Azure SSML은 화자·속도·피치·스타일을 표현하지만 적용 범위는 음성별로 확인해야 한다. 지원하지 않는 style이 중립으로 처리될 수 있으므로 응답 성공만으로 감정 적용을 판정하지 않는다. Pleos에 이 SSML을 전달하는 설계도 아니다. [공식 SSML 제어 설명](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-synthesis-markup-voice)

문서 조회 외 서비스 호출은 하지 않았다. 지역별 실제 가용성, 생성물 저장·재배포 조건, 모델 변경 정책, 가격과 차량 내 사용 조건은 후속 도입 검토 항목이다. 현재 외부 담당 협의·payload 확정은 사용자 지시에 따라 보류한다.

## 캐릭터별 레시피와 후보 승인

호스트는 캐릭터와 승인된 발화 요청을 넘긴다. provider 이름이나 SDK별 파라미터를 발화마다 선택하지 않는다. 아래는 아직 구현하지 않은 로컬 API 스케치다.

```text
recipe = selectVoiceRecipe(characterId, creativeTraits, catalogRevision, selectionSeed)
collection.saveCharacterWithRecipe(character, recipe)
session.submit(approvedSpeech, storedRecipe)
```

`collection`은 저장 소유자의 계약을 표시하는 가칭이다. TTS가 컬렉션 DB를 추가한다는 뜻은 아니다. 실제 공개 시점에는 캐릭터와 레시피가 함께 저장됐는지 확인해야 한다. `selectVoiceRecipe`가 기존 ID를 다시 받으면 저장된 결과를 사용하고 추첨하지 않는다.

| 로컬 개념 | 필수 내용과 규칙 |
| --- | --- |
| `CharacterVoiceRecipe` | `recipeId`, 버전, 캐릭터 ID, 생성 요청 ID, 선택 seed, catalog revision, 창작용 음성 특성, binding. 새 여정은 새 생성 요청 ID를 사용하고 같은 요청의 재시도는 같은 레시피를 사용 |
| `VoiceBinding` | `PleosDefault` 또는 `CatalogVoice`로 구분. 후자는 승인 candidate ID, provider, 정확한 voice ID, 모델 식별 정보, locale, 검수한 제어 preset을 가진다. 빈 voice ID를 성공으로 표현하지 않음 |
| `VoiceCandidate` | 지원 언어·mode·기기, 실제 확인한 제어, 청취 표본 digest, 검수 결과, 사용 권리 근거 참조, 승인 catalog 버전. 상태는 검토중·승인·신규선택중지·사용중지로 구분 |
| `VoiceAvailability` | 준비중, 사용가능, 사용불가와 사유. 저장된 binding과 분리해 네트워크 단절이 캐릭터 ID나 화자를 바꾸지 않게 함 |
| `VoiceAsset` | recipe digest, 원문 UTF-8 digest, 적용 preset, format, 파일 digest, 생성 출처, 보존·삭제 정보. 정확한 원문과 binding이 일치하는 파일만 재생 |
| `AppliedVoice` | 요청 특성과 실제 provider·화자·적용 제어·무시한 제어·대체 사유. 희망 metadata를 실제 적용값으로 복사하지 않음 |

recipe ID가 같아도 동일 파형을 보장하지는 않는다. 외부 서비스가 모델 버전을 고정하지 못하면 그 한계를 기록하고, 이미 수집한 클립은 허용된 보존 범위에서 파일 digest로 보존한다. provider의 변경은 기존 캐릭터를 몰래 재추첨하는 계기가 될 수 없다.

생성 모델은 창작용 특성만 제안한다. 실제 voice ID·제어값·파일 위치는 신뢰된 catalog에서 해석하며 모델이 반환한 임의 ID나 URL을 실행하지 않는다. 검수된 제어 범위를 벗어난 제안은 후보 선택에 쓰지 않는다. 외부 합성이 승인되는 단계에서는 텍스트 외부 전송 동의를 서버 기록 동의와 구분한다. 전송이 허용되지 않는 `finalText`는 몰래 축약·비식별화하지 않고 원문 그대로 가능한 로컬 경로나 무음을 선택한다.

캐릭터 모티브와 음성 관계는 다음과 같은 합성 시안으로 비교한다. 세 시안은 예시이며 화자 ID를 아직 배정하지 않는다.

| 합성 여정·형태 | 성격과 원하는 소리 | 피할 표현 |
| --- | --- | --- |
| 휴식 목적, 물결 무늬를 품은 둥근 반투명 오브젝트 | 포근한 중간 음역, 또렷한 짧은 문장, 안정된 리듬 | 속삭임 때문에 잘 안 들리는 소리, 바다가 실제 보인다는 단정 |
| 전시 관람, 겹친 선 무늬를 품은 작은 반투명 오브젝트 | 호기심 있는 가벼운 리듬, 선명한 자음 | 지나치게 높은 피치, 운전 중 질문 연발 |
| 친구 방문, 따뜻한 빛을 품은 조약돌 형태의 반투명 오브젝트 | 느긋한 온기, 부드러운 문장 끝 | 둔탁해서 숫자가 뭉개지는 소리, 어린아이 흉내를 귀여움의 필수 조건으로 삼기 |

외형의 크기·색과 목소리를 성별·연령으로 기계적으로 연결하지 않는다. 실제 청취 비교가 배정을 결정한다. 같은 화자군을 공유해도 외형·이름·성격·리듬 조합은 다를 수 있다. 음색 차이가 사용자에게 구별되지 않으면 새 음성으로 세지 않는다.

감정은 캐릭터의 기본 화자를 유지한 채 승인된 작은 표현 범위만 바꾼다. 미지원 감정은 같은 화자의 검수된 중립 표현으로 낮추고 실제 적용 내역에 남긴다. `STARTLED`를 비명이나 차량 경고음으로 변환하지 않는다. 창작 preset이 미확인 운전 사실을 발화하게 해서는 안 된다.

## 실패와 복원의 동작

| 상황 | 제안 동작 |
| --- | --- |
| 생성 대기·실패 상태에서 출발 | 출발을 막지 않고 음성을 준비중 또는 사용불가로 둔다. 완료 알림이 재생 명령이 되지 않는다 |
| 재시도·reroute·앱 재시작 | 저장된 캐릭터·recipe·catalog revision을 복원한다. 큐와 과거 `SpeechRequest`는 복원하지 않는다 |
| 후보 또는 캐시 파일 누락 | 정확히 같은 binding으로 복원 가능한 자산만 다시 확보한다. 불가능하면 사용불가로 표시하고 다른 화자를 무작위 선택하지 않는다 |
| 합성 전에 네트워크가 없음 | 같은 recipe와 원문에 해당하는 검증된 로컬 파일이 있으면 새 승인 요청으로 재생한다. 없으면 무음. 캐릭터를 다른 화자로 읽지 않는다 |
| 합성·재생을 시작한 뒤 실패·timeout | 해당 요청을 종료한다. 같은 문장을 Pleos로 자동 재전송하지 않는다. 사용자가 다시 요청할 때 새 ID·시각·현재 정책을 검사한다 |
| 취소 뒤 늦게 자산이나 콜백 도착 | 취소 세대의 결과는 재생하지 않는다. 저장 가능한 일반 자산인지와 지금 재생할 수 있는지는 별도 판단이다 |
| 기존 화자 사용중지·provider 퇴역 | 캐릭터의 원래 binding을 보존한 채 사용불가 사유를 남긴다. 권리 제한이면 해당 자산도 중지·삭제한다. 새 binding은 실제 주차 상태의 명시적 변경과 새 revision으로 다룬다 |
| 사용자 음성·저장 동의 철회 | 재생·진행 작업을 취소하고 허용 범위를 벗어난 캐시를 제거한다. 서버 ACK나 삭제 재시도가 발화를 유발하지 않는다 |

플랫폼 기본 음성이 필요하면 출발 전 또는 도착 후 사용자가 선택하는 별도 `기본 안내 음성`으로 제공하는 안을 둔다. 이것은 캐릭터가 같은 목소리를 유지했다는 성공 사례에 포함하지 않는다. 기본 안내도 새 요청과 기존 정책을 거친다.

## 구현 경계와 첫 단계

TTS core는 recipe 해석·승인 후보 선택·요청 검증·정책·큐·실제 적용값을 소유한다. Android voice는 Pleos 연결과 향후 파일 player·포커스·중단·콜백을 소유한다. AVATAR는 외형과 창작용 성격 특성을 제공하고, 컬렉션 저장 소유자는 캐릭터와 recipe의 원자적 보존을 맡는 안을 제안한다. 서버의 생성 작업·자산 저장은 SERVER와 PM의 후속 설계 대상이다. 이번에 소유권이나 외부 계약을 확정하지 않는다.

현재 `AndroidVoiceSession`은 내부에서 Pleos provider를 생성한다. C를 붙이려면 provider 주입 경계와 로컬 재생 adapter가 필요하다. `EngineMode.SERVER`는 Pleos 내부 mode이므로 외부 공급자를 뜻하도록 재사용하지 않는다. 미래 이벤트에서 provider 식별과 Pleos mode를 구분한다. 여러 player를 붙여도 승인·TTL·중복·포커스를 판단하는 큐는 하나로 유지한다. 생성 작업은 재생 큐 밖에서 진행하고, 캐시 준비 중 포커스를 잡거나 기존 3초 시작 timeout을 늘리지 않는다.

wire 1.0은 그대로 둔다. 기존 `voiceProfileId`는 나중에 로컬 registry 참조로 연결할 수 있지만 recipe·자산·생성 작업 계약을 대체하지 못한다. `additionalProperties: false`인 기존 JSON에 provider 설정을 임의로 넣지 않는다. 새 경계의 버전과 저장 형식은 내부 시안이 확인된 뒤 PM이 정한다.

다음은 구현 승인을 받은 뒤의 순서다. 이번 요청에서는 실행하지 않았다.

1. TTS core에 세 합성 캐릭터와 비실행 후보 catalog를 넣는 결정적 recipe 선택 실험을 만든다. 같은 생성 ID의 재시도·reroute·재시작에서 같은 binding, 다른 새 여정에서 새 recipe ID, 미승인 후보 제외를 확인한다. 음색 생성 성공으로 표현하지 않는다.
2. 후보별 청취 평가를 통과한 짧은 파일 묶음으로 B를 시연한다. 승인 텍스트와 파일 매칭·정책·취소를 실제 player에서 검증한다. 목소리와 외형을 함께 평가해 C의 후보를 줄인다.
3. 외부 호출이 별도 승인된 뒤 C의 provider 한 개만 제한적으로 연결한다. 세 화자 레시피와 같은 화자의 기본 문장·새 문장을 검증하고 단절·취소·보존 조건을 검사한다. 여러 외부 공급자를 동시에 붙이지 않는다.

기존 전역 동일 화자를 요구하는 테스트는 향후 캐릭터 내부의 동일 화자 보존 테스트로 바꾼다. 원문·근거·UNKNOWN·TTL·중복·포커스·늦은 콜백 테스트는 유지한다. 변경 전에 현재 [62개 정책 테스트](../../../android/feature/tts/src/test/kotlin/ai/nunti/tts/SpeechSystemTest.kt)와 [8개 fixture 검사](../../../android/feature/tts/src/test/kotlin/ai/nunti/tts/IntegrationFixtureTest.kt)를 기준선으로 둔다.

## 실제 청취와 재생 검증 계획

이번에 확인한 [PM 복원 보고](/Users/pig30nidae/NUNTI/docs/handoff/restoration/2026-11-02/PM.md)에는 JVM62·fixture8·실제 바이너리 컴파일, 주차 SDK 완료, lifecycle, 실제 D 전환 거부·취소와 P 복귀가 기록돼 있다. PM의 새 실행은 `-no-audio`였으므로 새 PCM·청취 증거는 아니다. 과거 Virtual Console inactive는 이번 환경에서 해소됐지만 속도>0의 별도 발화 요청, 통화·내비·안전음 경합, 실제 주행 허용 발화는 여전히 별도 검사다. 기존 [TTS 런타임 검토](../../handoff/restoration/2026-11-02/tts-evidence/runtime-review.md)와 구분해 보존한다.

청취 실험은 다음 안을 제안한다. 수치는 초기 비교 실험의 수용 후보이며 제품 출시 기준으로 확정한 값이 아니다.

- 한국어 청취자 5명 이상이 세 캐릭터의 소리를 평가한다. 공통 승인 문장 30개를 각 후보에 동일하게 사용한다. 숫자·날짜·합성 도로명, 짧은 인사, 여섯 논리 감정, 공백·줄바꿈을 보존한 리포트를 포함한다. 실제 주소는 쓰지 않는다.
- 먼저 이름·provider를 숨긴 음성 단독 비교로 발음·첫 음절·자연스러움·피로감을 평가한다. 이후 2.5D 시안과 함께 외형 적합성·귀여움·다시 듣고 싶은 정도·소장 의향을 각각 5점으로 평가한다. 순서는 섞고 비교용 음량을 맞추되 원본 파일도 보존한다.
- 예비 통과선은 숫자·날짜의 의미 오류와 첫 음절 누락 0건, 자연스러움·외형 적합성·귀여움의 청취자별 중앙값을 모은 중앙값 4점 이상으로 제안한다. 개인별 점수·오류 문장·탈락 이유를 함께 남긴다. 평균 하나로 발음 결함을 감추지 않는다.
- 같은 캐릭터의 중립·기쁨·차분한 표현이 같은 화자로 들리는지 ABX 비교를 한다. A·B에는 다른 두 캐릭터의 중립 표본, X에는 그중 한 캐릭터의 감정 표현을 놓는다. 서로 다른 세 캐릭터를 음성만으로 구별하는 3지선다도 실시한다. 총 정답률 80%를 예비 목표로 두되 표본 수와 개인차를 공개한다. 음색 분리가 실패하면 후보를 다시 고른다.
- 채택 후보는 각 cold·warm·offline 조건에서 유효 요청 30회 이상을 별도 측정한다. 첫 가청 샘플 지연, SDK callback 지연, 취소→무음 시간, 실패율, p50·p95, 초기화·연결 횟수를 분리한다. 반복은 정상 cooldown과 새 요청을 지키며 중복 방지 기능을 끄지 않는다.

가청 지연은 submit 시각과 같은 시간축에 정렬한 PCM 또는 loopback으로 측정한다. 파형 onset 기준·잡음 임계값·시계 오차·출력 경로를 기록한다. 주차 스피커 출력과 에뮬레이터 gRPC 캡처는 별도 표본이다. SDK `onStart`나 기존 41ms·73ms·231ms·57ms를 가청 지연으로 쓰지 않는다. 새 인증 gRPC 캡처 도구 복원이 선행 작업이며 기존 `reference-ko.wav`의 Yuna 음성과 180ms padding은 Pleos 증거가 아니다.

실제 파일 재생 또는 외부 합성 연결 후에는 사용자 중지·background·D 전환·통화·내비·안전음·suspend·단절·TTL 만료·늦은 합성 응답을 각각 검사한다. 이벤트 취소와 실제 무음 도달을 함께 확인한다. 캐릭터 재선택이나 네트워크 복구로 같은 발화가 다시 나오면 실패다. 모델·화자 변경은 위 청취 검사의 재평가 사유다.

현재 설계 보고를 막는 미제공 외부 payload는 없다. 다음 실행을 막는 것은 승인된 캐릭터 음성 후보와 청취 결과의 부재, 새 PCM 캡처 도구, provider별 실제 제어·보존 조건의 미검증이다. 첫 내부 구현은 외부 호출 없이 결정적 레시피 선택과 복원 경계부터 확인할 수 있다. 외부 담당 협의·운영 배포·실차 승인은 후속 단계로 남긴다.
