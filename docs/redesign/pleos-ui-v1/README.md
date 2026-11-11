# 눈티 Pleos UI 리디자인

기존 TOZI 파일의 [Redesign · Pleos UI 페이지](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=15-4)에 편집 가능한 디자인을 제작했다. 기존 앱의 기능과 데이터 계약을 조사하고 실제 에뮬레이터를 캡처해 비교했다. 이번 결과는 Figma 설계이며 production 화면 코드, 서버 API, 저장된 캐릭터를 변경하지 않았다.

## 디자인 열기

| 상태 | 낮 | 밤 |
| --- | --- | --- |
| 출발 전 | [Figma](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=24-221) · [PNG](exports/pre-trip-day.png) | [Figma](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=24-660) · [PNG](exports/pre-trip-night.png) |
| 변형·결과, 정차 중 | [Figma](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=24-416) · [PNG](exports/reveal-parked-day.png) | [Figma](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=24-812) · [PNG](exports/reveal-parked-night.png) |
| 주행 제한 시 정적 제안 | [Figma](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=24-530) · [PNG](exports/driving-restricted-day.png) | [Figma](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=24-926) · [PNG](exports/driving-restricted-night.png) |
| 여정 종료 후 | [Figma](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=24-600) · [PNG](exports/post-trip-day.png) | [Figma](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=24-996) · [PNG](exports/post-trip-night.png) |

메인 프레임은 실제 앱 창과 같은 **1682 × 1210**이다. [830 × 1210 좁은 창](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=26-454)도 네 상태의 낮·밤 버전으로 제작했다. 플랫폼의 상태 표시, 차량 정보, 내비게이션과 공조 영역은 앱 UI로 만들지 않았다.

## 추천 방향

[UI A / 여정 카드](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=22-149)를 추천한다. 승인된 눈티와 경로를 같은 카드 안에서 보여줘 입력이 캐릭터의 변화로 이어진다는 관계를 읽기 쉽다. [UI B / 경로 중심](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=22-339)은 경로 확인을 먼저 보여주지만 눈티의 존재감이 작다. 두 안 모두 같은 입력과 버튼을 유지했다.

여기서 UI A는 추천 시안이다. 사용자가 이미 승인한 캐릭터 A 원화와 별개의 UI 선택이며, production 기본 디자인 승인을 받았다고 취급하지 않는다.

## 구성과 편집 가능성

최종 페이지에는 36개 화면 프레임이 있다.

- 핵심 네 상태 × 낮/밤 × 두 창 너비: 16개
- 출발 전 A/B 방향 비교: 2개
- 로딩·오프라인·경로 없음·에셋 실패 × 낮/밤: 8개
- 기존 경로 도구 × 낮/밤: 2개
- 함께하기 직후 정차 상태 × 낮/밤 × 두 너비: 4개
- 여정 옵션·생성 방식 × 낮/밤: 4개

실제 Figma readback에서 Auto Layout 노드 716개, 컴포넌트 인스턴스 326개, 보이는 텍스트 588개를 확인했다. 이미지 레이어 30개는 승인된 기본 눈티와 바다·호기심 PNG 두 종의 재사용이다. 화면 전체를 이미지로 넣은 레이어는 없다. [구조 검증](figma-structure-verification.md)에 노드별 근거가 있다.

공식 Pleos Connect 2.1.5의 [디자인 키트](https://www.figma.com/design/ZZ4WoyC5NQvducpb2Iv8Uw)와 [디스플레이 가이드](https://www.figma.com/design/QWCJAx4Sp0UWawRDuOOjsv)를 실제로 가져왔다. 미공개 컴포넌트는 key import가 되지 않아 Figma UI의 native copy/paste로 5세트·60개 variant를 보존했다. 메인 화면은 공식 버튼·입력·스위치·체크박스 인스턴스를 재사용한다. 원본 세트는 페이지 오른쪽 참조 영역에 분리했다.

색상은 Day/Night semantic 변수와 primitive alias로 연결했다. 글자·간격·모서리도 변수 및 텍스트 스타일로 구성했다. 현재 CSS의 `--bg`, `--paper`, `--ink` 등과 대응하며, `NuntiColors.*` 같은 Android code syntax는 후속 구현 이름 제안이다. 해당 Kotlin 클래스가 이미 존재한다고 가정하지 않는다. [토큰 표](token-table.md)를 참고한다.

## 기존 동작 보존

생성은 기존 `POST /v3/avatars`와 자동 저장을 유지한다. 별도 저장 API나 저장 버튼을 추가하지 않았다. '새 여정 만들기'는 입력 화면으로 돌아가며 기존 입력과 저장 결과를 삭제하지 않는다.

'눈티와 함께하기'는 기존 native bridge와 검증된 캐시를 통해 여정을 시작한다. 새로 만든 정차 중 ACTIVE 화면에서만 '여정 마치기'를 제공한다. 자동 도착 판정이나 자동 여정 종료를 추가하지 않았다. '눈티로 돌아가기'와 '여정 마치기'는 서로 다른 동작으로 유지한다.

음성 듣기, 주행 음성 준비, LIVE/DEMO 선택, 진행 중인 여정·마지막 리포트, 생성 방식, 경로 파일·사진·내비·API 입력을 옵션과 경로 도구 화면에 남겼다. 캐릭터 보관함은 주행 기록 목록과 구분한다. 기록을 서버에 새로 동기화하는 기능은 설계에 넣지 않았다.

Figma의 42개 프로토타입 반응은 명시적 클릭으로만 작동한다. 주요 생성→결과→함께하기→정차 후 종료→리포트 흐름과 옵션 열기/닫기를 연결했다. 입력 필드·기분·차량 데이터는 디자인용 예시이며, Figma가 실제 API나 CarUxRestrictions를 호출하는 것은 아니다. 모든 데이터 동작을 실행하는 앱 프로토타입으로 주장하지 않는다.

4초 모션의 실제 원본과 Android debug 구현은 [이전 모션 결과](../birth-motion-v1/README.md)에 보존돼 있다. 이번 UI의 REVEAL은 정착한 결과 상태를 보여주며, 재생·건너뛰기·모션 축소의 배치와 연결 지점을 설계했다. 이번 UI 페이지 자체에 모션을 중복 복제하지 않았다.

현재 `LOCAL_LAYERS`의 production 결과는 정적이다. 새 모션 연결과 주야간 테마 적용은 후속 구현이다. 승인 A 모드가 아닌 기존 캐릭터와 과거 저장 이미지는 각 기록의 원본을 유지해야 한다.

## 실제 비교와 자동 수정

- [기존 앱 ↔ Figma 비교 보드](comparison/before-after-day.png)
- [낮 ↔ 밤 비교 보드](comparison/day-night-proposals.png)
- [화면별 차이](comparison-notes.md)
- [실제 에뮬레이터 검증](runtime-verification.md)
- [기존 화면·상태 목록](screen-inventory.md)
- [Kotlin·WebView·API 연결표](kotlin-mapping.md)

비교 중 발견한 문제를 수정했다. 야간 보조 버튼의 검은 글자 렌더링은 공식 버튼 인스턴스와 명시적 색상 연결로 고쳤다. 바깥쪽 stroke가 잘리던 버튼은 안쪽 stroke로 바꿨다. 입력 행 높이를 122로 맞춰 아래 테두리 잘림을 없앴고, 도착 후 카드의 중복 문장을 줄여 버튼 아래 여백을 확보했다. 좁은 창의 경로 미리보기 잘림도 수정했다. 좁은 변형 화면은 모든 조작이 첫 화면에 들어오도록 조정했다.

현재 수동 스크롤이 필요한 주된 화면은 좁은 출발 전 입력이다. 주요 생성 버튼은 스크롤 영역 밖에 고정된다. 주행 화면 네 개에는 스크롤·모션·프로토타입 반응이 없다.

## 검증 결과와 한계

| 확인 | 결과 |
| --- | --- |
| Figma 실제 구조 | 36개 프레임, 13개 검사 PASS. 승인 이미지·폰트·인스턴스 연결·터치 영역·화면 경계 검증 |
| 토큰 대비 | 텍스트 42쌍 ≥4.5:1, 활성 컨트롤/focus 후보 8쌍 ≥3:1. 최저 텍스트 4.85:1 |
| 조작 크기 | 외곽 터치 영역 최소 76, 주요 버튼 높이 80 Figma px. 이 에뮬레이터는 160dpi |
| 비교 이미지 | 실제 앱 4개 crop과 Figma 8개 원본 픽셀 보존. 출력 14개 재생성 해시 일치 |
| 현재 설치 앱 | 기존 빌드 APK SHA와 설치 APK SHA 일치. 실제 입력·결과·ACTIVE·종료·연결 실패 캡처 |
| 주행 제한 | 실제 D/30에서 `requiresDO=true`, restrictions `80`, `canFinish=false` 확인 |
| 데이터 복원 | 기존 마지막 리포트 원본 SHA 일치 복원. P/0·창 크기·공조·Console 상태 원복 |

현재 에뮬레이터는 ACTIVE 주행 중 플랫폼 차단 화면을 표시한다. Figma의 정적 주행 UI는 플랫폼이 앱 표시를 허용할 때를 위한 제안이다. 차단을 해제하거나 우회하지 않았으며, 현재 기기에서 이 UI가 주행 중 보인다고 주장하지 않는다.

디자인의 실제 Android 적용, 자동 주야간 전환, TalkBack 조작, 글자 확대, 실차의 물리적 글자 높이, 새 UI의 CPU·메모리·프레임 성능은 아직 검증하지 않았다. Figma 대비 계산과 기존 앱 빌드 확인을 새 Android UI의 성능 통과로 취급하지 않는다.

다음 구현은 기존 WebView와 JourneyActivity에 이 토큰과 배치를 적용하고, 기존 Canvas 모션을 생성 완료 결과에 연결하는 순서가 적절하다. 서버·점수 엔진·주행 서비스는 재작성할 필요가 없다. 주행 화면 노출은 플랫폼의 실제 허용 조건을 별도로 확인해야 한다.

## 원화와 제작 기록

원화 owner는 Nunti 프로젝트이며 승인 A의 출처·프롬프트·버전은 [identity asset manifest](../identity-refine-v1/asset-manifest.json)에 있다. 본 UI는 [기존 기본 합성 PNG](../../../android/app/src/debug/assets/nunti_motion_v1/base.png)와 [바다·호기심 결과](../route-variants-v1/samples/coast-curious/character.png)를 그대로 재사용했다. 새로운 이미지 생성, 유료 모델 호출 또는 매 주행 이미지 생성은 수행하지 않았다.

공식 자료의 owner, 원본 URL, SHA256, 버전, 이용 범위는 [공식 asset manifest](official-assets/manifest.json)와 [출처](sources.md)에 기록했다. 원본 키트를 공개 라이브러리로 발행하거나 재배포 권리를 새로 주장하지 않았다.

`figma-*.js`는 실제 MCP 제작에 사용한 단계별 코드다. `*-result.json`은 반환된 노드 ID 기록이며, 단계 중 시각 수정으로 제거된 노드는 최신 구조 readback을 기준으로 판단한다. 기존 페이지에 생성 코드를 무조건 다시 실행하지 않는다. 다음 검증 도구는 저장된 실제 산출물에 대해 재실행할 수 있다.

```sh
python3 scripts/verify_nunti_ui_tokens.py
python3 scripts/verify_nunti_figma_ui.py --verify
.worktrees/server/backend/.venv/bin/python scripts/build_nunti_ui_comparison.py --check-only
```

실제 Figma를 다시 읽으려면 검증 스크립트의 `--emit-reader`로 reader를 생성하고 Figma MCP에서 실행한 결과를 저장한 뒤 검사한다. [PNG별 Figma 출처](exports/frame-sources.json)와 [추가 화면 출처](exports/extra-frame-sources.json)에 파일·노드·치수를 기록했다.
