# 승인 비주얼의 기존 앱 통합

작업 브랜치: `codex/nunti-visual-integration`. main에 병합하지 않았다. 시작 시 이미 변경되거나 추적되지 않던 기능·자산은 보존했다. `before-integration-source-state.json`과 `before-integration-git-status.txt`가 이번 작업의 기준이다.

## 유지한 경계

- Studio는 기존 WebView이며 입력·보관함·음성·내비·여정 bridge를 유지한다. Journey는 기존 Android View이며 서비스·점수 엔진·세션·기기 보고서 계약을 유지한다.
- `/v3/avatars` 요청과 응답, `variantContext`, `AvatarSpec`, 이미지 SHA, 캐릭터 자동 저장과 재시도 식별자는 변경하지 않는다. 서버 기본 renderMode도 그대로다. UI의 초기 선택만 가용할 때 승인 A의 `LOCAL_LAYERS`로 바꾼다. 다른 생성 방식과 이전 보관 캐릭터도 계속 열 수 있다.
- 서버 변경은 공식 Noto Sans KR `.ttf`를 기존 정적 파일 라우트에서 허용한 한 항목뿐이다. 기존 생성·음성·경로 API를 다시 작성하지 않았다.
- `staticOnly=true`, `AvatarSpec.motion=none`은 보관된 최종 그림과 기존 Journey 포즈 정책에 그대로 남는다. 새 정차 reveal은 버전·레이어 해시를 확인한 별도 표시 기능이다. 기존 formation이나 주행 중 포즈를 활성화하지 않는다.

## 승인 원화와 변신

원본 `docs/redesign/identity-refine-v1/nunti-a-front-transparent-v1.png`, 서버 레이어 `backend/nunti/avatar_studio/assets/nunti-a-layers-v1`, 기존 debug motion의 무손실 분리 자산을 재사용한다. `scripts/package_nunti_production_assets.py`는 승인 공통 자산 24개, 약 1.12MB를 `prototypes/avatar_generator/nunti-motion/`에 복사하고 해시·크기·투명 영역 경계를 기록한다. 새 그림 생성·색 보정·리샘플링은 없다.

실제 응답의 `destinationMotif`, `roadMotif`, `routeVariant`, `expression`, `layers`, `layerAssets`로 필요한 레이어를 고른다. 9개 샘플 ID를 런타임 lookup으로 사용하지 않는다. 유효한 기존 매핑 버전과 전체 원본 해시를 확인하지 못하면 실제 최종 PNG를 정적으로 표시한다. 레이어 파일도 바이트 수·SHA256·768×768 크기를 검증한 뒤 메모리에 캐시한다.

Figma 모션 [A · 빛길](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=4-13)의 7개 트랙을 기존 Canvas 기술에 적용했다. 4000ms, cubic-bezier(.4, 0, .2, 1), 경로 450–1300ms, 스카프 1300–1900ms, 포켓 1700–2500ms, 표정 2850–3050ms를 보존한다. 고정 몸체는 투명도 1과 같은 좌표를 유지한다. 국소 빛은 원본의 두 원과 투명도만 사용한다. Figma 편집기의 반복 미리보기와 달리 실제 앱은 한 번 재생하고 정지한다.

끝 프레임은 재조합한 근사 그림이 아니라 해당 서버 응답의 원본 PNG다. Skip·모션 축소·제한 중단도 이 이미지를 표시한다. 최종 PNG 실패 시 승인 base로 바꾸며 원본 보관 데이터는 수정하지 않는다.

## 화면·오프라인·접근성

[승인 UI](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=24-221)의 두 열 카드, 80px 주요 조작, 76px 선택 항목, 주야간 색상과 로컬 Noto Sans KR를 적용한다. HTML과 네이티브 모두 실제 앱 창 1682×1210 및 좁은 창 830×1210을 기준으로 한다. 플랫폼 내비게이션·차량 정보 영역은 앱에 복제하지 않는다.

기존 Studio 정적 UI를 APK에 포함하고 같은 localhost URL에서 읽는다. API와 `/v3/assets`는 기존 서버로 연결한다. 따라서 서버가 꺼져도 기본 눈티와 입력 화면은 표시되지만 새 생성·보관함 조회·새 여정 준비까지 오프라인 기능으로 바뀐 것은 아니다. 현재 결과의 디코딩된 PNG는 같은 페이지의 제한 복귀 시 재사용한다. 네이티브 여정은 기존 검증된 파일 캐시를 계속 사용한다.

모션 축소는 사용자 선택을 로컬 저장하고 OS animator 설정과 `prefers-reduced-motion`도 따른다. 시스템에서 강제하면 켜진 스위치를 비활성화한다. 자동 반복·자동 재개는 없다. 실제 경로와 SDK 출처는 유지하며 합성 예시를 실제 내비 geometry로 표시하지 않는다.

공식 글꼴 원본과 OFL은 `assets/fonts/noto-sans-kr.ttf`, `OFL.txt`에 함께 보관한다. 출처는 [Google Fonts Noto Sans KR](https://github.com/google/fonts/tree/main/ofl/notosanskr)다. 전체 variable 폰트를 포함하므로 약 10MB의 APK 원본 자산 증가가 있다.

실제 첫 실행에서는 WebView의 DPR이 1.375여서 1682×1210 창을 1224×880 CSS viewport로 배치했다. headless 기준만 통과한 상태의 잘림을 실제 스크린샷에서 발견했다. `useWideViewPort`를 켜고 호스트가 측정한 창 너비와 역 DPR을 viewport에 전달해 수정했다. 시스템 density나 차량 제한은 바꾸지 않았다. 재설치 후 실측은 1683×1210 CSS, visual scale 0.727312이며 너비 1px은 반올림 차이다. 네이티브 화면은 기존 density 계산을 유지한다. 추가로 가변 폰트의 기본 Thin 축을 명시적 wght 400/500/700으로 고정하고, 넓은 화면 부제의 잘림을 없애기 위해 제목 영역을 120으로 확보했다.

## 차량 제한

기존 `StudioCarGate`의 실제 P·유효 속도·CarUxRestrictions·전경 조건을 유지한다. UX callback 외에 기어·속도 callback을 연결해 제한 변화에 즉시 대응하며, property 오류는 허용 상태로 해석하지 않는다. 주행 제한을 변경하는 override나 DO 선언 추가는 없다.

모션은 매 프레임 허용 상태와 전경 여부를 확인한다. 제한·화면 이탈·Skip·모션 축소는 대기 중인 레이어 로딩도 취소한다. 주차 복귀와 늦은 생성/이미지 응답이 모션을 다시 시작하지 않는다. 다른 렌더러로 전환하면 이전 레이어 renderer의 캔버스 소유권도 해제한다.

이 방식은 [Pleos UI 가이드](https://document.pleos.ai/en/docs/connect/guide/docs-design/Introduction/intro) 및 [CarUxRestrictions 구현 가이드](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-developer-guide/driving-restriction-development-guide)를 따른다. DO 선언을 플랫폼 승인 증거로 해석하지 않는다. 실제 주행 화면의 플랫폼 차단 여부와 성능 수치는 최종 runtime 보고서를 기준으로 한다.

## 검증 범위

컴파일·JVM·백엔드·JavaScript 경계 테스트와 실제 에뮬레이터 증거를 구분해 기록한다. headless browser의 치수 검사나 VM Canvas stub 통과만으로 실제 주행 표시·GPU 성능·픽셀 일치를 판정하지 않는다. 최종 결과는 이 폴더의 README와 runtime/regression 기록에서 집계한다. 물리적 차량 디스플레이의 mm 단위 가독성과 실제 차량 CPU/GPU는 별도 검증이다.
