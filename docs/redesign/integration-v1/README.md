# 눈티 비주얼 통합 보고서

승인 A 원화·결정적 변형·4초 변신·Pleos Figma 화면을 기존 Studio WebView와 네이티브 Journey에 통합했다. 브랜치는 `codex/nunti-visual-integration`이며 main에 병합하지 않았다. 유료 이미지·영상·음성 생성 API 호출은 0회다.

## 결과물

- [승인 UI Figma](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=24-221), [4초 변신 Figma](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=4-13)
- [이번 통합의 수정 파일 목록](changed-files.md), [구현과 기존 계약 연결](implementation-notes.md), [변경하지 않은 계약 파일 해시](preserved-contracts.json)
- [실제 앱에서 그린 기본·9개 변형 비교](comparison/character-runtime-matrix.png), [캐릭터 비교 출처·해시](comparison/character-runtime-manifest.json)
- [실제 앱 이전/이후 4개 화면](comparison/before-after-actual-day.png), [Figma와 실제 앱 비교](comparison/figma-vs-actual-day.png), [시각 검토·차이](comparison/README.md)
- [기존 원본·A/B 비교](../identity-refine-v1/comparison-board.png)
- [최종 APK](../../../android/build/app/outputs/apk/debug/app-debug.apk), [설치·자산 일치 증거](installed-build.json)
- [최종 앱의 변신 시연 영상](runtime-display-optimized/production-motion.mp4), [최종 화면·시스템 모션 검사](runtime-display-optimized/report.json)
- [런타임 검증 상세](runtime-verification.md), [기기·설정·기존 기록 복원](final-device-state.json), [전체 파일 해시 목록](files-manifest.json)

## 유지한 기능

기존 생성·자동 저장·보관함·내비 입력·기기 음성·LIVE/DEMO 여정·점수·기기 리포트를 보존했다. 서버의 요청/응답 schema, 원화 매핑과 생성 결과 저장 방식은 바꾸지 않았다. 기존 보관 캐릭터도 원래 그림으로 표시한다. UI 기본 선택만 서버 capability가 지원할 때 승인 A로 바뀐다.

같은 입력은 기존 서버 mapper가 같은 AvatarSpec으로 변환한다. production 모션은 이 실제 응답과 공통 레이어를 사용한다. 샘플 9개만 lookup하는 방식이 아니다. 몸체는 고정되며 경로 무늬→목적지 장식→표정 순으로 변한다. 최종·Skip·모션 축소 프레임은 해당 요청의 실제 생성 PNG다.

실제 CarUxRestrictions·P·속도·전경 상태로 재생을 제한한다. 주행 제한, 화면 이탈, Skip, 모션 축소는 대기 중인 레이어 로딩도 취소하고 자동 재개하지 않는다. 서버가 꺼져도 APK에 든 입력 화면·기본 눈티는 표시한다. 새 생성·보관함 조회·새 여정 준비에는 기존 서버가 필요하다.

## 빌드와 회귀

| 검증 | 결과 | 증거 |
|---|---|---|
| Android debug 빌드 | 성공, 최종 APK SHA `fe8781a6…` | `optimized-package-build.log`, `installed-build.json` |
| 앱 JVM 테스트 | 10/10, 새로 실행 | `app-tests-final.log` |
| 점수·여정·신호 gate JVM | 18/18, 새로 실행 | `regression-baseline/score-results.json` |
| 백엔드 | 395 passed, 104 subtests passed | `regression-backend-final/report.json`, `backend.log` |
| JavaScript | 기존 UI 5 suite + 모션 + formation, 7 suite 통과 | `regression-js-optimized/report.json` |
| 모션 경계 검사 | 14/14 | 동일 JS 보고서. 실제 자산 바이트·해시, Canvas는 VM stub |

Android SDK의 일부 deprecated callback 경고와 기존 pytest dependency 경고는 남아 있지만 빌드·테스트 실패는 아니다. APK는 기존 데이터를 지우지 않고 `adb install -r`로 설치했다. APK와 프로젝트의 정적 파일 해시도 확인했다.

## 실제 기기 검증

Pleos Emulator `Nunti_Restore_2_1`, Android 사용자 10, 2560×1440 디스플레이에서 실행했다. 실제 앱 창은 1682×1210, 좁은 창은 830×1210이다. 최초 실행에서 발견한 WebView DPR 차이·네이티브 폰트 Thin 축·부제 잘림은 수정 후 재설치했다.

보정 APK `322015…`에서 Studio 실제 검사 31종을 확인했다. 첫 실행의 CDP promise 수거로 검증 도구가 중단됐으나 앱 예외 증거는 없었다. 완료된 22개와 동일 APK의 continuation 10개에서 중복 1개를 제외해 31개다. 실패 로그는 삭제하지 않았다.

- 9개 실제 LOCAL_LAYERS 생성 결과, 서버 SHA 및 같은 브라우저에서 디코딩한 최종 그림과 768×768 PNG 픽셀 일치
- 실제 생성 완료 후 4초 재생·완료, Skip, 사용자 모션 축소 및 유지
- Virtual Console의 실제 D 전환 중 모션 중단, P 복귀 후 자동 재생 없음
- 실제 이미지 404 시 기본 눈티, 오프라인 현재 결과 유지, 오프라인 APK 화면 진입
- 이미지·음성 모델 생성 POST 없음

이 증거는 `runtime-studio-calibrated/`와 `runtime-studio-calibrated-continuation/`에 있다. `production-pixel-verification.json`은 9개 최종 RGBA 일치와 0/1000/2200/3000/4000ms 보호 몸체 영역의 픽셀 변화 0을 확인한다.

최종 APK의 `runtime-display-optimized/report.json` 실제 기기 검사 7종은 주야간, 좁은 창, 백그라운드 중단·복귀, OS 모션 축소·복원, 실제 영상 기록을 확인했다. 시스템 animator 설정이 미설정인 경우 검증 도구가 문자열 `null`로 복원하려던 오류도 수정했고 원래 키 상태와 실제 모션 허용 상태를 각각 확인했다. 이 검증 도구 오류를 앱의 재생 오류로 분류하지 않는다.

`runtime-native-final/`의 실제 도착 화면에서는 폰트 굵기와 부제 잘림 수정, 낮/밤·830 창을 확인했다. 원본과 개선본의 점수·목적지는 서로 다른 실제 검증 여정의 값이다. 비교 이미지의 숫자 차이는 점수 알고리즘 변경을 뜻하지 않는다.

최종 APK `fe8781a6…`의 `runtime-optimized-final/report.json`은 12/12 통과했다. 실제 form POST를 서버 도달 전에 통제된 HTTP 503으로 한 번 실패시키고, 입력·기본 눈티·동일 requestId를 유지한 재시도가 실제 LOCAL_LAYERS 생성으로 성공함을 확인했다. 실제 서버 장애가 발생했다고 주장하지 않는다. 추가로 최종 4000ms 완료, 비음수 첫 프레임, Skip, 모션 축소, 실제 D 전환 중 중단·옵션 창 닫힘, P 복귀 후 자동 재생 없음도 확인했다.

`runtime-native-fallback-final/report.json`은 2/2 통과했다. 없는 이미지 파일 경로를 검증 소유 리포트에만 일시 적용해 승인 base와 접근성 설명을 확인하고 원래 latest.json을 바이트 단위로 복원했다. 새 여정을 시작하거나 기존 기록을 교체하지 않았다.

`runtime-endpoints-final/report.json`은 최종 APK에서 9개 최종 상태의 픽셀 일치를 다시 확인했다. 이미 생성한 검증용 결과를 사용했으며 이 검사에서 생성 API 호출은 없다. 최종 캐릭터 비교 보드도 이 9개 캡처로 갱신했다.

최종 MP4는 2560×1440, 약 6.99초이며 그 안에 4초 변신과 앞뒤 정지 화면이 담겨 있다. macOS AVFoundation으로 실제 파일을 디코딩하고 [0–5초 프레임 보드](runtime-display-optimized/video-frames-final/contact-sheet.png)를 직접 검토했다. 재생 중 몸체가 유지되며 무늬·장식 뒤에 표정이 바뀌는 것을 확인했다. 프레임 시각과 크기는 [디코딩 기록](runtime-display-optimized/video-frames-final/decoded-frames.json)에 있다.

## 에뮬레이터 성능

불필요한 DOM 갱신과 WebView 배율이 중복 적용된 Canvas 크기를 줄였다. 같은 9종 레이어 캐시가 준비된 상태에서, 화면 녹화와 분리해 측정했다. [전후 측정](performance-comparison.json)의 최종 PSS는 약 146.2 MiB로 이전 약 152.2 MiB보다 줄었다. 모션 중 앱 CPU 샘플은 코어 하나 기준 37–56%, 정지 후 2%였다.

Canvas 갱신은 4초 동안 121회, 평균 30Hz였지만 Android gfxinfo의 지연 프레임은 75.21%였다. 기존 계산 방식으로도 47.11%였고, 프레임 시간 p95는 34ms였다. Canvas callback 빈도와 실제 표시 프레임의 부드러움은 다른 측정이다. 메모리 감소는 확인했지만 부드러움 개선은 입증하지 못했으므로 성능 검증은 미완료다. 최종 시연 영상은 별도로 기록한 실제 앱 화면이며 합성 영상이 아니다.

## 제한과 남은 검증

실제 D/30 상태에서는 기존과 동일하게 Pleos의 “주행 중에는 사용할 수 없습니다” 화면이 앱을 가린다. 모션 중단과 서비스 상태는 확인했지만 주행 동반 UI가 운전자에게 표시되는 것은 검증하지 못했다. 기존 DO 선언을 추가·확대하거나 플랫폼 제한을 우회하지 않았다. 배포 환경의 허용 정책 확인이 필요하다.

실차의 물리적 mm 가독성, 실차 CPU/GPU·장시간 열·배터리 특성, TalkBack 음성 탐색과 시스템 글자 크기 확대는 미검증이다. 에뮬레이터 화면·접근성 라벨·대비 점검을 실차 인증으로 해석하지 않는다. 유료·로컬 모델 생성 방식은 기존 mock 회귀까지만 확인했고 새 모델 호출로 재생성하지 않았다.

다음 단계는 플랫폼의 주행 표시 허용 조건을 확인하고, 실제 대상 기기에서 모션의 표시 프레임 지연을 추적하는 것이다. 최종 승인 전까지 현재 작업 브랜치를 유지한다.

테스트 중 생성한 눈티는 검증용 이름과 requestId로 분리했다. 기존 캐릭터를 삭제하지 않았다. 차량·공조·주야간·창 크기·시스템 모션 설정·마지막 기기 리포트의 복원 결과는 runtime 기록에서 확인한다.
