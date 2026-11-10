# 생성·주행·리포트 통합

2026-11-05 작업 기준: `d42cefb`의 생성기와 `8b497df`에서 추가된 점수 모듈.

## 여정의 소유권

`JourneySession` 하나가 `sessionId`, `characterId`, `routePlanId`, 입력 출처, 시작 시각을 소유한다. 생성한 캐릭터를 새 점수 화면의 고정 캐릭터로 교체하지 않는다. 같은 캐릭터의 이미지와 음성 자산은 SHA-256으로 확인한 뒤 Android 내부 저장소에 보관한다.

흐름은 생성·보관함 선택 → **눈티와 함께하기** → 차량 신호 → `ScoreEngine` → 감정·음성 → 주차 후 **여정 마치기** → 최종 리포트다. 기존 점수 진단 화면은 라이브러리에 유지하되 별도 사용자 런처는 제거했다.

| 경계 | 구현과 책임 |
|---|---|
| 생성·목소리 | 기존 로컬 서버가 캐릭터와 불변 음원을 보관한다. |
| 입력·점수 | `PleosSignalSource`와 팀원의 `ScoreEngine`이 신호 및 점수를 계산한다. 기존 가중치와 임계값은 유지한다. |
| 여정 수명 | `JourneyService`가 1초 간격 입력을 유지한다. 내비 전면 전환과 Activity 종료는 여행 종료가 아니다. |
| 표시 | `JourneyActivity`가 생성된 원본 그림, 감정 상태, 점수를 표시한다. 감정 변화에 색·표식·짧은 움직임을 적용한다. 생성 이미지의 얼굴을 새로 그리는 구현은 아니다. |
| 음성 | 같은 캐릭터의 합성 인사 음원을 참조해 중립·걱정·안도·기쁨 대사를 미리 만든다. 음원이 없는 감정은 화면으로만 알린다. 다른 음색으로 몰래 대체하지 않는다. |
| 종료·저장 | P·정차·UX 허용 상태에서 종료한다. 최종 리포트를 먼저 저장하고 음성을 재생한다. |

## 입력과 복원 규칙

- LIVE는 실제 Pleos 서비스 콜백이다. 에뮬레이터의 Console 값도 이 경로로 들어온다. 실차 검증을 뜻하지 않는다.
- DEMO는 점수 담당의 `Scenarios.recovery`를 10배속 재생한다. Console이나 GPS를 움직이지 않는다.
- 미수신 값은 `null`로 유지한다. 평가할 정보가 없으면 점수 대신 **평가 불가**를 표시한다.
- 네 문이 모두 닫혔다고 판단하려면 네 문 모두의 수신값이 있어야 한다.
- 이전 세션의 늦은 콜백은 세대 번호로 거부한다. 변화가 있을 때만 오는 신호는 침묵만으로 만료하지 않는다. 연결 해제와 오류는 미수신으로 처리한다.
- 감정 대사는 상태 변화와 30초 간격을 기준으로 발행한다. 고유 key를 재생 전에 기록해 같은 갱신으로 재발화하지 않는다.
- `onRouteEnded()`는 경로 계산 완료다. 여행 도착이나 종료로 사용하지 않는다.
- 앱 프로세스가 중단되면 마지막 저장 리포트를 **중단됨**으로 연다. 자동 재출발이나 이전 음성 재생은 없다. 정상 실행 중 최대 5초마다 저장하므로 강제 중단 직전 일부 입력은 유실될 수 있다.
- 최종 리포트는 Android 내부 `files/journeys/`에 있다. 서버로 주행 기록을 동기화하는 API는 이번 통합에 포함하지 않는다.

## 음성 API

`GET /v3/avatars/{characterId}/feedback-voice/{kind}`는 보관된 음원만 읽는다. `POST`는 없을 때 무료 로컬 모델로 합성한다. `kind`는 `NEUTRAL`, `WORRY`, `RELIEF`, `JOY`다.

응답은 `characterId`, `kind`, `text`, `profileId`, `planSha256`, `referenceAudioSha256`, `audio`를 포함한다. 소유자 인증, 캐릭터별 잠금, 참조·출력 해시 확인을 적용한다. 인사 음원이나 원래 합성 캐시가 없으면 새 음색으로 대체하지 않고 오류를 반환한다. 주행 서비스는 합성 요청을 하지 않는다.

현재 멘트는 점수 담당의 네 감정 문구다. 점수를 숫자로 읽거나 사건별로 자유로운 코멘트를 만드는 기능은 별도다. 점수 기준 자체도 팀원 문서의 초안 상태다.

## 내비 이동의 범위

Virtual Console의 차량 신호와 Android GPS는 별도 입력이다. 현재 공식 공개 NaviHelper에는 GPS 주입이나 모의주행 시작 함수가 없다. `SIMULATION_GUIDING` 상태값만으로 시작 기능이 지원된다고 판정하지 않는다.

Android Emulator는 **Location → Routes → Play route**와 GPX/KML 재생을 지원한다. 기존 검증은 Android GPS 주입에 성공했지만 NaviHelper 위치 이동을 확인하지 못했다. Console 속도 수신, 내비 전면에서의 점수 유지, 내비 경로 위 차량 이동을 각각 검증해야 한다.

- [Virtual Console 공식 안내](https://document.pleos.ai/en/docs/connect/guide/getting-started/application-development/use-vehicle-emulator)
- [NaviHelper 공식 소개](https://document.pleos.ai/en/api-reference/connect-sdk-pleos/NaviHelper/intro)
- [Android 위치·경로 재생](https://developer.android.com/studio/run/emulator-extended-controls)
- [기존 GPS·내비 검증 결과](../design/navigation-integration/RESULT.ko.md)

## 검증 상태

Debug·Release APK 빌드, lint, 점수·세션 단위 테스트 18개를 통과했다. 음성 관련 Python 테스트 38개와 하위 검사 35개를 통과했다. 기존 아주대학교 눈티의 인사 음원을 참조한 실제 로컬 감정 음원 4개가 생성됐으며 모두 동일한 참조 SHA를 사용한다. 음성의 주관적 품질 승인을 뜻하지 않는다.

실제 Android 통합 검증 결과는 `scripts/verify_integrated_journey.py`와 `.local/integration-2026-11-05/runtime-verification.json`으로 확인한다. 보고서가 없거나 실패하면 실제 통합 완료로 보고하지 않는다. 녹화·유료 API는 사용하지 않는다.

2026-11-05 실제 실행은 **전체 FAIL**이다. 같은 캐릭터의 DEMO 481표본·종료 저장과 실제 감정 WAV 재생을 확인했으나, LIVE의 D·30km/h 유지 조건이 시간 초과했다. 시험 여정은 종료했고 Console의 D·속도0·페달0·조향52를 읽어 원복 확인했다. 내비 전면에서의 기록 유지 단계에는 도달하지 않았다. 사용자가 우선 목표를 **기본 내비 지도에 이동을 실제 반영하는 시연**으로 다시 명확히 했으므로, 추가 통합 확대를 멈추고 GPS/NMEA 입력 경계를 조사한다.
