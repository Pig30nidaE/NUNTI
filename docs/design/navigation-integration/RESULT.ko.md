# 사진 없는 내비 API 연결 검증 결과

2026-11-04, 준비된 Mac과 Pleos 에뮬레이터 기준이다. **현대 내비의 실제 목적지·현재 위치를 가져와 별도 도로 API로 경로를 계산하고, Android에서 눈티를 생성·보관·복원하는 흐름을 확인했다.** 실행 방법은 [테스트 안내](TESTING.ko.md)를 따른다.

[기존 추천 구현·시험 순서](../../research/2026-11-04-navigation-review/README.md)는 1번 SDK 읽기, 2번 전체 형상 확인, 3번 snapshot 반복, 4번 선택 GPS 재생이다. 요청한 1~3번은 사진 없는 API 방식으로 구현·검증했다. 2번은 현대 전체 도로 형상을 수신한 것이 아니라, 별도로 계산한 OSRM 형상의 출발·도착·방향을 확인하는 대안으로 구현했다. 추가 4번에서 남은 SDK 위치 수신·재탐색 완료 한계와 구분한다.

## 완료한 검증

- **실제 Android 화면 23개 검사 통과.** 내비 목적지 수신, 전체 도로 형상, 생성 전 확인, 생성·보관·재시작 복원, 저장 경로 재생, 이미지·음성 설정 보존을 확인했다. 세 여정은 서로 다른 캐릭터 ID와 이미지 SHA를 만들었다. 이 실행은 `LOCAL_RENDER` 빠른 일러스트 모드다. [화면 검증 보고서](../../../.local/navigation-integration/ui/verification.json)와 같은 폴더의 `*-artifact.json`에 입력·결과가 있다.
- **실제 SDK 콜백 수신.** 현대 내비 초기 대화상자를 해소한 뒤 콜백 32개, `ROUTE_GUIDING`, 유효한 목적지·현재 위치·routeId를 확인했다. `CONNECTED`만으로 데이터 수신을 성공 처리하지 않는다. [SDK 수신 기록](../../../.local/navigation-integration/native-gps-ready.json).
- **현대 내비에서 정상 런처로 복귀하는 동작 통과.** 같은 SDK 세션과 화면에 표시 중인 캐릭터·이미지·음성 설정을 유지한다. 내비 복귀 때 host가 다시 생성되던 문제를 수정하고 에뮬레이터의 실제 Android 화면에서 확인했다. [앱 전환 검증](../../../.local/navigation-integration/handoff/verification.json).
- **실제 외부 도로 조회 3회 성공.** 이후 반복 실행은 캐시를 사용했다. [원본 계획과 정확한 공급자 응답](../../../.local/navigation-integration/live/)에 전체 WGS84 좌표, 원 응답 바이트 SHA, 정규화 SHA를 보관했다. JSON 숫자의 `0.0` 표현을 보존하도록 Python으로 원본을 저장했다.
- **무료 로컬 AI 새 그림 생성과 실제 Android 복원 완료.** 실제 안목해변 API 경로 108점을 49점으로 정규화한 입력으로 `FLUX.2-Klein-4B 4bit`를 실행했다. 44.2초에 512×512 RGBA 이미지를 만들고 이미지 SHA·원본 경로 보존·측정한 alpha 외곽을 확인했다. Android에서 같은 이미지 SHA와 음성 설정을 복원했고 측정된 탄생 형상도 사용할 수 있다. 현재 앱은 이 AI 결과 화면으로 테스트를 준비했다. [AI 검증 보고서](../../../.local/navigation-integration/local-ai/verification.json), [Android 복원 보고서](../../../.local/navigation-integration/local-ai/android-restore.json), [생성물 메타데이터](../../../.local/navigation-integration/local-ai/artifact.json), [생성 이미지](../../../.local/navigation-integration/local-ai/avatar.png).
- **GPS 세 점 주입·읽기·복원과 눈티 보존 확인.** 공식 에뮬레이터 API에서 세 점을 모두 다시 읽었고, GPS 상태 7개 필드를 복원했다. SDK의 원상태 복귀 관측, 캐릭터 ID·이미지 SHA·음성 설정 보존도 확인했다. 원 OSRM 응답→SHA→정규화→GPX와 방향 반전·왕복 진단 파일 검증을 통과했다. 이 결과는 아래 SDK 위치 수신·재탐색 완료의 미검증과 구분한다. [GPS 실행 보고서](../../../.local/navigation-integration/replay/20261103T163707Z-3da98920/verification.json).
- **UI 상태 회귀 8개 통과.** 입력 변경과 지연 응답의 충돌, 내비 경로 변경 후 재확인, 계획의 좌표·목적지 변경, 차량 화면 제한을 검사했다. 실제 UI 스크립트를 사용하되 DOM·내비·HTTP 경계는 시험용으로 대체한 회귀 검사다. [UI 상태 보고서](../../../.local/navigation-integration/ui-state-tests.json).
- **최종 Android debug·release 빌드와 lint 통과.** 내비 복귀 처리 수정 후 25초에 빌드를 마쳤고, 위 23개 화면 검사도 다시 통과했다. 어댑터는 `onRouteEnded`를 경로 탐색 완료 `READY`로 해석한다. [빌드 로그](../../../.local/avatar-generator/build.log). 로컬 release APK는 서명 전 시험 파일이며 제출 완료본이 아니다.
- **백엔드 전체 260개와 10 subtests 통과.** 원본·응답 SHA, 등비율 변환·Y 반전·RDP 512점 제한, 확인 전 생성 차단, 저장 계획과 좌표·목적지 일치, 소유자 격리, 재생·기존 캐릭터 보존, 요청 제한을 포함한다. 의존 라이브러리의 TestClient deprecation 경고 1개가 있다. [전체 로그](../../../.local/navigation-integration/backend-tests.txt).

실제 도로 응답의 원본 점 수와 생성 입력의 정규화 점 수는 다음과 같다.

| 여정 | 원본 점 | 정규화 점 | 계획 |
| --- | ---: | ---: | --- |
| 현대 내비 현재 위치 → 더현대서울 | 395 | 88 | [native-plan.json](../../../.local/navigation-integration/live/native-plan.json) |
| 서울역 → 서울시청 | 100 | 58 | [seoul-plan.json](../../../.local/navigation-integration/live/seoul-plan.json) |
| 강릉역 → 안목해변 | 108 | 49 | [coast-plan.json](../../../.local/navigation-integration/live/coast-plan.json) |

이 검증의 유료 API 호출, 사진 추출 호출, 영상 녹화, 스피커 녹음은 모두 0회다. 경로 API·NaviHelper·로컬 생성·기기 TTS에 외부 API 키는 필요 없다.

## 미검증인 항목

- **SDK의 주입 위치 수신과 재탐색 완료는 미검증이다.** 세 점 GPS는 에뮬레이터와 Android GPS에 반영됐지만, SDK 위치는 중간·도착에서 갱신되지 않았다. 오차는 각각 약 10.48km·19.36km다. 재탐색 명령은 접수됐지만 `onReRouteEnded` 완료 콜백은 확인하지 못했다. 현대 내비를 앞에 두고 GPS를 16초 유지한 마지막 분리 시험에서도 SDK는 판교 위치에 머물렀다. 해당 GPS도 복원했다. [전면 실행 분리 시험](../../../.local/navigation-integration/replay/foreground-1793723987927571000/verification.json). GPS 주입 성공만으로 내비 연동 전체 통과를 표시하지 않는다.
- 현대 내비 선택 경로와 OSRM 형상의 일치, 실제 차량 동작, 생성 일러스트의 귀여움·소장 욕구, 운전습관 개선 효과는 미검증이다. AI 생성물은 `humanQualityApproved=false`를 유지한다. 새 그림 생성·복원 성공은 사용자의 미적 품질 승인을 뜻하지 않는다.

## 미구현과 공급자 제약

NaviHelper 3.0.5의 공개 API와 `getInternalApi()`에서 전체 도로 polyline을 받는 방법은 확인되지 않았다. 확장 인터페이스는 `updateOccupiedRegion(Rect)`만 공개한다. 요약 경유지·목적지를 도로 형상으로 이어 붙이지 않았다. 현대 SDK 문맥과 `OSRM_FOSSGIS` 형상을 분리해 저장하며 `geometryMatchesHyundaiRoute=false`로 표시한다.

새 TTS 음색 생성과 Anna 음색 재현은 미구현이다. 지금은 생성물에 맞춘 설정으로 기기의 기존 한국어 TTS를 재생하며 자동 발화하지 않는다. 공개 OSRM 주소를 상용·대량 운영에 쓰는 전환도 완료하지 않았다. 현재 공개 서버 시험은 1.1초 간격과 작업공간 누적 12회로 제한한다.

목적지 이름을 위경도로 변환하는 지오코딩은 구현하지 않았다. 현대 내비에서 장소를 검색해 가져오거나 공개 장소 시험 좌표를 입력한다.

## 같은 검사를 다시 실행하기

실제 Android 화면 검사는 앱을 열고 내비의 초기 대화상자를 마친 뒤 실행한다. 첫 명령은 캐릭터 세 개를 새로 생성한다. 기존 계획의 도로 형상은 캐시에서 읽는다.

```sh
node scripts/verify_navigation_ui.mjs
node scripts/test_navigation_ui_state.mjs
```

백엔드 검증은 외부 HTTP를 호출하지 않는다.

```sh
cd /Users/pig30nidae/NUNTI/backend
../.worktrees/server/backend/.venv/bin/python -m pytest -q
```

빌드는 저장소 루트에서 `python3 scripts/run_avatar_generator.py --build --local-ai --navigation-api --restart-server`로 다시 실행한다. GPX 준비와 GPS·재탐색 실행 옵션은 [테스트 안내](TESTING.ko.md)에 있다.
