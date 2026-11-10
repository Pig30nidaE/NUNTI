# 이번 통합에서 수정한 파일

작업 시작 전 이미 존재한 dirty/untracked 기능을 이번 변경으로 계산하지 않는다. 시작 상태는 `before-integration-source-state.json`과 `before-integration-git-status.txt`에 기록했다.

## 앱과 표시 기능

| 파일 | 변경 |
|---|---|
| `android/app/build.gradle.kts` | 기존 Studio 정적 UI와 승인 자산을 APK에 포함. examples·검증용 mjs는 제외 |
| `android/app/src/main/AndroidManifest.xml` | Studio 크기·주야간 재배치와 Journey 주야간 변경 처리. DO 선언 변경 없음 |
| `android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt` | APK 정적 파일 제공, 주야간·시스템 모션 축소·실측 viewport 전달, 기어·속도 제한 callback |
| `android/app/src/main/kotlin/ai/nunti/app/journey/JourneyActivity.kt` | 승인된 주행·정차·도착 UI, 폭·테마 대응, 기기 기록 상세, 기본 그림 fallback |
| `android/app/src/main/kotlin/ai/nunti/app/journey/JourneyCompanionView.kt` | 원본 그림 FIT 표시, 제한·백그라운드 시 기존 포즈 중단 |
| `android/app/src/main/kotlin/ai/nunti/app/journey/NuntiTheme.kt` | 신규. 승인 색상과 굵기 축을 명시한 로컬 폰트 캐시 |
| `prototypes/avatar_generator/index.html` | 기존 ID·입력·동작을 보존한 출발·결과·보관함 구조, 옵션 dialog, Skip·모션 축소·재연결 |
| `prototypes/avatar_generator/studio.css` | 승인된 주야간 토큰·타이포·카드·반응형 레이아웃 |
| `prototypes/avatar_generator/ui-redesign.js` | 신규. 기존 DOM 동작을 보존하는 화면·선택·테마·실측 viewport adapter |
| `prototypes/avatar_generator/studio.js` | 승인 A 초기 선택, 기존 API 결과에 레이어 변신 연결, 정적·오프라인·이미지 실패·취소 처리 |
| `prototypes/avatar_generator/nunti-transformation.js` | 신규. 버전/해시 검증, 4초 Canvas 모션, 실제 최종 PNG, Skip·모션 축소·취소 |
| `backend/nunti/avatar_studio/api.py` | 정적 파일 허용 확장자에 `.ttf` 추가. 생성·저장·모델·서버 계약 변경 없음 |

## 자산

- `prototypes/avatar_generator/nunti-motion/`: 기존 승인 PNG 24개 복사본과 manifest.json / manifest.js. 실제 이미지별 SHA와 출처는 manifest에 기록한다.
- `prototypes/avatar_generator/assets/pleos-check.svg`: 공식 Figma checkbox export.
- `prototypes/avatar_generator/assets/fonts/noto-sans-kr.ttf`, `OFL.txt`: 공식 Google Fonts variable 폰트와 라이선스.

원본 승인 master·서버 레이어·기존 비교 보드·debug motion 자산을 교체하거나 수정하지 않았다.

## 재실행·회귀 검증

- `scripts/package_nunti_production_assets.py`: 승인 자산을 검증하고 production bundle을 생성.
- `scripts/test_nunti_transformation_state.mjs`: 실제 자산 바이트를 사용하는 모션·취소·계약 경계 테스트.
- `scripts/test_avatar_layers_ui_state.mjs`: 승인 A UI 기본값 및 실제 handler의 상태 검증 갱신.
- `scripts/test_navigation_ui_state.mjs`: 기존 DOM/native gate를 반영한 테스트 harness 보완.
- `scripts/verify_nunti_integration_regression.py`: 백엔드·JS·JVM 회귀 실행기.
- `scripts/nunti_integration_runtime_lib.mjs`, `scripts/verify_nunti_integration_studio.mjs`, `scripts/verify_nunti_integration_journey.mjs`, `scripts/verify_nunti_integration_display.mjs`: 실제 에뮬레이터·Virtual Console 검증 도구.
- `scripts/verify_nunti_integration_final.mjs`, `scripts/verify_nunti_integration_endpoints.mjs`, `scripts/verify_nunti_integration_native_saved.mjs`: 최종 APK의 실패·재시도·gate, 9개 최종 픽셀, 네이티브 이미지 누락 검증.
- `scripts/build_nunti_integration_comparison.py`: 실제 baseline/Figma/통합 화면 비교 보드와 출처 manifest.
- `scripts/verify_nunti_integration_pixels.py`: 실제 production Canvas의 최종 이미지와 중간 프레임 고정 몸체 픽셀 검증.
- `scripts/verify_nunti_video_frames.swift`: macOS AVFoundation으로 실제 녹화 파일을 디코딩하고 프레임·메타데이터 추출.
- `scripts/write_nunti_integration_manifest.py`: 이번 통합 범위의 파일 경로·해시·시작 상태 비교를 기록.

실행 중 추가되는 검증 도구·결과의 전체 경로는 최종 `files-manifest.json`을 기준으로 한다. `docs/redesign/integration-v1/`에는 이번 통합 보고서·로그·스크린샷·영상이, `docs/redesign/pleos-ui-v1/integration/`에는 headless UI 검증 자료가 추가됐다.
