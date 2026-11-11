# 변형 시스템 검증 기록

2026-11-09. 코드 자동 검사와 실제 Pleos Android WebView 실행을 구분해 기록한다. [검증 결과 JSON](verification-results.json)에도 집계를 저장했다.

## 자동 검사

| 검사 | 결과 |
| --- | --- |
| 새 API·매핑·실제 PNG 합성 | 43 passed |
| 기존 Studio·경로 API·음성 디자인·로컬 모델 회귀 | 72 passed, 35 subtests passed |
| 전체 Python 실행 | 115 passed, 35 subtests passed, 15.02초 |
| 새 레이어 UI 상태 | 13 passed |
| 기존 생성·컬렉션·음성 UI 상태 | 32 passed |
| 전체 UI 상태 | 45 checks passed, Node 실행 파일 4개 |
| 새 Python 파일 Ruff | 통과 |
| `git diff --check` | 통과 |
| Android `:app:compileDebugKotlin`, `:app:assembleDebug` | 오프라인 빌드 통과, 에뮬레이터에 업데이트 설치 |

Python 실행에는 기존 Starlette TestClient/httpx 사용 중단 예정 경고 1건이 있었다. 테스트 실패는 없다. UI 상태 검사는 Node VM의 제어된 DOM·HTTP 대역을 사용한다. 실제 레이아웃 검증으로 간주하지 않는다.

다음 항목은 실제 번들 PNG와 런타임 합성기를 사용해 확인했다.

- 9개 변형 PNG가 서로 다르며 모든 결과의 기본 6개 레이어 SHA256은 같다.
- 같은 입력을 반복·병렬·별도 프로세스에서 합성해 PNG와 명세가 같다.
- 요청 UUID만 바꾼 HTTP 생성 결과의 PNG 해시가 같다.
- 기존 LOCAL_RENDER의 재생성 동작은 유지된다.
- 경로 없음 및 모든 선택값 누락은 패키지 기본형과 픽셀이 같다.
- 경로 수정은 fingerprint에 반영되고 몸체·얼굴 앵커는 유지된다.
- 손상·누락 에셋, 누락 manifest, 잘못된 크기·버전·앵커는 완전한 기본형으로 복구된다.
- 활성 에셋과 fallback이 모두 손상되면 명시적으로 실패한다.
- day/night는 배경 메타데이터만 바꾸며 PNG는 같다.
- 소켓과 urllib 연결을 차단한 상태에서도 합성과 샘플 내보내기가 된다.
- 기존 저장소와 미디어 URL로 PNG와 AvatarSpec JSON을 실제 저장·조회한다.
- 차량 권한이 해시 계산 중 철회되면 새 생성 요청을 보내지 않는다. 정지 결과는 formation·idle RAF·replay를 시작하지 않는다.

[샘플 일관성 보고서](samples/consistency-report.json)에 Python/Pillow 버전과 공통 레이어 해시를 저장했다. 9개 경로 무늬는 모두 다른 경로를 보장하는 식별 수단이 아니다.

## 실제 Pleos 실행

`emulator-5554`의 2560 × 1440 화면에서 테스트했다. 플랫폼의 차량 정보·내비게이션·하단 공조 영역은 그대로 두고 앱의 실제 멀티윈도 영역에서 실행했다.

기존 Studio 서버와 컬렉션을 보존하기 위해 임시 저장소의 별도 로컬 서버를 사용했다. 실제 앱의 WebView, 네이티브 주차 허용 상태, 기존 폼 제출과 컬렉션을 통해 확인했다. 샘플 경로만 사용했고 이미지 API·지도 API·음성 합성을 호출하지 않았다. 종료 시 기존 세션 쿠키와 ADB reverse 연결을 복원했다.

| 화면 | 증거 |
| --- | --- |
| 입력 | [01-layered-input.png](runtime/01-layered-input.png) |
| 실제 생성 결과 | [02-layered-result.png](runtime/02-layered-result.png) |
| 컬렉션 | [03-layered-collection.png](runtime/03-layered-collection.png) |
| 경로 없음 기본형 | [04-no-route-base.png](runtime/04-no-route-base.png) |

[실행 보고서](runtime/report.json)의 9개 검사를 통과했다. 실제 폼의 선택값과 목적지·길·기분이 렌더러에 전달됐고, 결과 canvas를 900ms 간격으로 읽어 픽셀이 그대로임을 확인했다. 컬렉션에서 같은 이미지를 다시 열고, 경로 없는 응답의 기본형과 영수증도 확인했다. 첫 입력 캡처에 이전 프레임이 남은 문제는 화면 갱신 대기를 추가하고 전체 과정을 다시 실행해 해결했다.

검증 도구는 [verify_nunti_layers_live.mjs](../../../scripts/verify_nunti_layers_live.mjs)다. 이 스크립트는 실행 중인 테스트 서버, `/private/tmp/nunti-layers-test-connection.json`의 임시 세션 정보, 실제 WebView의 CDP 포트 9237을 전제로 한다. 장치나 포트 구성이 다르면 그 환경에 맞게 준비해야 한다. 인증 정보는 프로젝트에 저장하지 않았다.

## 실행 명령

저장소 루트에서 실행했다.

```sh
PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python -m pytest -q \
  backend/tests/test_avatar_layered_api.py \
  backend/tests/test_avatar_layered_render.py \
  backend/tests/test_avatar_studio.py \
  backend/tests/test_avatar_route_api.py \
  backend/tests/test_avatar_voice_design.py \
  backend/tests/test_avatar_local_model.py

node --test \
  scripts/test_avatar_layers_ui_state.mjs \
  scripts/test_avatar_generation_ui_state.mjs \
  scripts/test_avatar_collection_ui_state.mjs \
  scripts/test_avatar_voice_ui_state.mjs
```

## 확인 범위의 한계

이번 작업은 승인된 A안을 기반으로 한 정지 변형 시스템이다. Figma 화면을 새로 작성하거나 Figma와 에뮬레이터를 픽셀 대조하지 않았다. 주차 상태의 실제 생성과 결과·컬렉션은 확인했지만 실제 운전 중 제한 전환, 실제 주행 경로 수신, TalkBack, UI 전체 명암 대비, 주야간 차량 테마, CPU·메모리·발열의 장시간 측정은 수행하지 않았다. 이를 차량 출시 승인이나 변신 애니메이션 검증으로 간주하지 않는다.

비교 보드에서 검토한 작은 크기의 한계는 README에 기록했다. 일관성은 레이어 해시와 고정 앵커로 검증했으며, 세 감정에 대한 사용자 인지 실험은 하지 않았다. 출처 원화의 권리는 프로젝트 제공 자료 기준이며 외부 권리 기록을 별도 확인하지 않았다.
