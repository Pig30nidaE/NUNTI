# API 없는 여정 MVP 시험

사용자는 여러 실제 생성 케이스를 아바타와 TTS까지 MVP 앱에서 시험하고, 끝난 뒤 직접 실행하기를 요청했다. 기존 C 반투명 기념 오브젝트와 Anna 선호를 유지한다. 외부 API·계정·새 모델 다운로드 없이 기존 로컬 Sohee 모델을 사용한다.

## 구현 선택

정적 생성 PNG를 앱에서 바꾸는 방식, WebView 미리보기, Android의 레시피 기반 Canvas를 비교했다. PNG는 현재 그림 한 장 외에 체형·표정 자산이 없고 API 없는 매번 생성을 제공하지 못한다. WebView는 실제 Compose·음성 정책 경로를 검증하지 못한다. 이번에는 레시피의 몸체·비례·재질색·내부 모티브·경로 무늬를 직접 그리는 Compose renderer와 기존 TTS 큐를 연결한다. 깊이가 다른 그림자·외피·빛·모티브·불투명 얼굴로 정적인 2.5D 표현을 만든다. 품질 승인을 자동 검사로 대신하지 않는다.

로컬 Python worker가 여정 입력→최초 캐릭터 레시피→실제 TTS WAV→불변 번들을 만든다. Android는 같은 번들의 시각 레시피를 직접 렌더링하고 같은 characterId의 파일을 기존 단일 큐에서 재생한다. Android 안에서 Qwen 모델이 실행된다고 표기하지 않는다. 신규 여정은 PC worker로 추가할 수 있고, 앱에는 재현 가능한 여러 사전 생성 시험 여정을 넣는다.

## 소유권과 계약

- AVATAR 담당은 새 `JourneyVisualSpec.kt`, `JourneyKeepsake.kt`만 작성한다. 기존 정책·고정 AvatarSpec·공통 앱은 변경하지 않는다.
- PC 담당은 `prototypes/journey_mvp`의 입력·번들 생성/검증 도구와 `.local/journey-mvp`의 새 상태를 소유한다. 기존 4개 생성 결과를 보존하며 복사한 상태에 새 케이스를 추가한다. 모델 작업은 한 프로세스만 실행한다. Android 자산에는 직접 쓰지 않는다.
- PM은 앱 카탈로그 경계·상태 저장·화면·라이프사이클·빌드·실제 앱 시험·실행 도구를 소유한다.

번들의 `characters` 항목은 `caseId`, `label`, `summary`, `characterId`, `journeyId`, `displayName`, `visual`, `visualSha256`, `recipeSha256`, `sourcePlanSha256`, `bindingId`, `voiceProfileId`, `directionSha256`, `clipIds`를 가진다. clipIds는 greeting/arrival/common 세 가지다. `visualSha256`는 정렬한 키·공백 없는 UTF-8 JSON의 SHA-256이다. `visual`은 다음 필드만 가진다.

```json
{"characterId":"nunti-...","seed":"16 lowercase hex","bodyFamily":"droplet","shapeId":"tilted_water_drop","palette":["#93D6CF","#F4C6A0","#FFF0D4"],"widthMultiplier":1.0,"heightMultiplier":1.0,"motif":"coastal_city","routePattern":"coastal","purpose":"rest"}
```

몸체는 기존 registry의 pebble/droplet/bean/sprout/pillow/lantern/cloud/acorn, 모티브는 art/coastal_city/mountain/forest/lakeside/city/unspecified, 경로 무늬는 coastal/mountain/urban/tree_lined/curving/highway/mixed/straight/unspecified, 목적은 rest/camping/exhibition/commute/visit/errand/unspecified다. 실제 선택 우선순위는 기존 registry 순서를 따른다. 별도 임의 디자인 필드를 만들지 않는다.

새 renderer의 공개 API는 `JourneyVisualSpec(characterId, seed, bodyFamily: JourneyBody, shapeId, palette, widthMultiplier: Float, heightMultiplier: Float, motif: JourneyMotif, routePattern: JourneyPattern, purpose: JourneyPurpose)`와 `@Composable JourneyKeepsake(spec, renderState: RenderState, modifier)`다. enum 값은 위 토큰의 대문자다. spec은 입력 검증을 소유하며 기존 Emotion 6개를 렌더링한다. `renderState.visible=false`면 접근성 내용까지 그리지 않는다. 애니메이션은 이번 범위에 넣지 않는다.

`bundle.json`은 schemaVersion=1, bundleId, rendererVersion, characters를 가진다. `voice/`는 기존 schemaVersion=2 Android 음성 manifest와 원본 WAV·라이선스를 보존한다. PC 출력은 `.local/journey-mvp/bundle`이고 PM이 검사 후 Debug assets의 `journey-mvp`로 전달한다. Android와 PC가 characterId·binding·profile·원문·음원 hash를 확인한다.

## 실제 통과 기준

서로 다른 목적·목적지·경로의 8개 여정과 모든 8개 몸체를 목표로 한다. 같은 경로의 다음 여정, reroute·재시도·앱 종료 후 외형/음성 보존, 인사·도착·공통 문장, 6표정, 밝은/어두운 배경, 64/128px 썸네일을 확인한다. 실제 Android에서 케이스 선택→renderer→같은 ID의 TTS→도착·저장→재시작 복원을 시험한다. 누락·변조 음원은 재생 거절, 이동·배경에서는 중지, 재시작·복원으로 자동 발화하지 않는다. 실차와 사람의 귀여움·소장 욕구·운전습관 개선 판정은 별도다.

기존 v1/v2/Sohee 원음·모델 pin·복원 증거는 변경하지 않는다. API·서버 wire·점수 의미·외부 담당 조율은 추가하지 않는다.

## 앱 시험 진입점

Debug launcher는 `ai.nunti.app.journey.JourneyMvpActivity`를 연다. 실제 Car feed는 자동차 feature가 있을 때만 연결하며 연결 실패로 일반 Android 시험 경로에 들어가지 않는다. 일반 Android에는 별도 `NON_AUTOMOTIVE_LAB` 출처를 명시한다. 명시적으로 조용한 음성 시험을 시작한 뒤에도 기존 audio mode/music 검사를 유지한다. 이 확인과 foreground 허가는 저장하지 않는다. 항상 LocalFileTtsProvider만 주입한다.

에뮬레이터 시험 Intent는 `mvp_action=select/greeting/common/arrival/arrive/save/reroute/stop/emotion/theme/force_block`을 받는다. `case_id`, `emotion`, `dark`, `blocked`가 관련 추가 값이다. `confirm_quiet_test=true`는 통제된 에뮬레이터 시험에서만 적용한다. 물리 기기에서는 이 자동화 진입점을 무시한다.

이벤트는 app-private `journey-mvp-events.jsonl`에 기록한다. MVP_READY에는 cases/bundleId, MVP_RESTORED에는 characterId/identity/stage/collectedCount, MVP_SELECTION과 MVP_REROUTE/MVP_SAVED에는 characterId/identity가 있다. MVP_PRESENTED는 characterId/identity/bodyFamily/shapeId/emotion/stage/visible/rendererVersion/visualVoiceJoined를 가진다. MVP_SPEECH_REQUEST는 requestId/clipId/characterId/profileId/audioSha256/textSha256/identity, MVP_SPEECH는 requestId/status/reason/providerId/profileId/speakerId/mode를 가진다. MVP_GATE는 source/motion/parked/visible/foreground/knownUX/requiresDO, MVP_ERROR는 reason을 기록한다. 자동화 로그는 UI의 실제 표시·PCM·사람 청취를 대신하지 않는다.
