# 실제 제작·실행 검증

2026-11-09. Figma 모션 원본, Android 빌드, 실제 Pleos 실행과 픽셀 대조를 각각 확인했다. 운영 기본 화면에는 아직 모션을 적용하지 않은 debug 프로토타입이다.

## 제작과 자동 검사

| 검사 | 결과·증거 |
| --- | --- |
| Figma 실제 키프레임·에셋·프레임 | 51개 통과. [보고서](figma-verification.json), [설명](figma-verification.md) |
| Android 상태·타이밍 테스트 | JUnit 10개 통과. [빌드 기록](runtime/build-report.json) |
| Android debug APK | `:app:assembleDebug` 통과, 기존 데이터를 보존해 업데이트 설치 |
| 모션 번들 재현 | 원본 해시, 목적지 레이어 무손실 분리, 기본형+9개 최종 합성 픽셀 일치. [기록](asset-verification.json) |
| 실제 Android 최종 픽셀 | 9개 모두 동일 Android decoder로 읽은 원본 결과와 완전 일치. 원본 PNG SHA256도 일치. [기록](pixel-verification.json) |
| 몸체 연속성 | 실제 0·1000·2200·3000·4000ms의 보호 영역 RGBA 변화 0 |
| Figma 정지 화면과 원본 | 동일 배경의 768² 비교에서 채널 최대 차이 2. 래스터 반올림 차이 |
| Figma 영상 프레임과 Native | 동일 배경으로 맞춘 평균 채널 오차 2/255 미만. H.264 색 압축과 2.2초 프레임의 실제 시점 2.1667초를 구분 |

최종 결과 검사는 PNG 파일 해시와 Canvas 픽셀을 구분한다. Android가 이미지를 읽을 때의 premultiplied alpha 반올림 때문에 원본 파일 바이트를 다시 인코딩한 PNG와 단순 비교하지 않는다. 같은 원본을 Android로 decode한 참조와 실제 Canvas draw 결과가 픽셀 단위로 같음을 확인했다.

## 실제 Pleos 실행

실제 기기는 `emulator-5554`, 사용자 10, 전체 2560 × 1440 / 160dpi다. 앱은 플랫폼이 배정한 1682 × 1210 영역에서 실행됐다. 차량 정보와 플랫폼 내비게이션·공조 영역은 앱 UI로 다시 만들지 않았다.

[실행 보고서](runtime/run-20261109T143534Z/report.json)의 29개 검사가 통과했다. Android 네이티브 Canvas를 실제로 실행했으며, 차량 허용 상태를 JavaScript나 Intent로 위조하지 않았다.

| 실제 확인 | 증거 |
| --- | --- |
| A 4초 실행 | [Android 화면 녹화](runtime/run-20261109T143534Z/light-trail-preview.mp4) |
| B 4초 실행 | [Android 화면 녹화](runtime/run-20261109T143534Z/quiet-color-preview.mp4) |
| 주간 최종 화면 | [화면](runtime/run-20261109T143534Z/screen-4000.png) |
| 건너뛰기 | [즉시 정지 결과](runtime/run-20261109T143534Z/skip-final.png) |
| 모션 축소와 선택 변경 후 설정 유지 | [정지 결과](runtime/run-20261109T143534Z/reduced-motion-final.png) |
| 재생 중 D·20km/h로 전환 | [플랫폼 제한 화면](runtime/run-20261109T143534Z/driving-restricted.png), [실제 UX 값](runtime/run-20261109T143534Z/restricted-ux.txt) |
| P 복귀 | [자동 재개하지 않은 상태](runtime/run-20261109T143534Z/park-return-state.json) |
| 다른 앱으로 전환 | [실제 BACKGROUNDED 중단 상태](runtime/run-20261109T143534Z/background-state.json) |
| 야간 정지 결과 | [전체 화면](runtime/run-20261109T143534Z/screen-night-final.png), [원본 프레임](runtime/run-20261109T143534Z/night-final.png) |
| 로딩 | [기본 눈티 유지 화면](runtime/run-20261109T143534Z/loading-base.png) |
| 에셋 실패 | [실패 안내와 기본 눈티 화면](runtime/run-20261109T143534Z/screen-failure-base.png), [원본 프레임](runtime/run-20261109T143534Z/failure-base.png) |
| 실제 창 너비 1682→830px 변경 | [세로 배치 화면](runtime/run-20261109T143534Z/resized-830px.png). 캐릭터와 7개 버튼이 앱 경계 안에 표시됐으며 기존 창 크기로 원복 |

공식 Virtual Console의 차량 입력으로 P→D→P를 전환했다. 실제 `CarUxRestrictionsManagerService`가 `requiresDO=true`, `activeRestrictions=80`으로 바뀌었고, 앱 재생 상태는 `SETTLED`, `animationRunning=false`, `stopReason=RESTRICTED`였다. 플랫폼 제한 화면도 표시됐다. 종료 시 기어·속도·조작값과 창 크기를 원복하고 검증용 heartbeat 연결을 닫았다. [환경 복원 기록](runtime/environment-restoration.json)과 [최종 조작 가능 상태](runtime/run-20261109T143534Z/screen-capture-return-state.json)를 보관했다.

첫 시도의 HOME 키는 Pleos에서 이 앱을 실제 배경으로 보내지 않았다. 검증 스크립트의 그 대기만 타임아웃됐으며 앱은 정상 완료했다. 기존 내비 앱으로 실제 전환하는 방식으로 고쳐 `onPause` 중단을 확인했다. [최초 시도 기록](runtime/run-20261109T143534Z/report-initial-home-key-timeout.json)은 최종 결과와 구분해 보존했다.

## 접근성과 시각 검토

실제 버튼은 높이 56–58dp이며 UI XML에서 확인했다. 화면 읽기용 캐릭터 설명과 모션 축소 상태 설명을 제공한다. 주야간 활성 텍스트 대비를 계산했고, 가장 낮은 주간 보조 텍스트도 4.73:1이었다. [계산과 Figma 속성 대조](figma-native-review.json)를 보관했다. TalkBack을 켜서 전체 조작을 수행하는 사용성 검증은 하지 않았다.

Figma는 캐릭터 모션의 768² stage를 담고, Android는 실제 차량 창 안의 조작 UI를 제공한다. 캐릭터 레이어의 좌표·타이밍·easing·빛 색은 일치한다. Figma 배경 `#F6F4EF`와 Android 주간 카드 `#EEF2E7`의 차이는 의도한 UI 배경 차이다. 픽셀 대조에서는 네이티브 투명 프레임을 Figma 배경에 올려 비교했다.

연결된 Figma 라이브러리에는 Pleos 컴포넌트가 없었고 MCP에는 공식 `.fig` 키트 import API가 없었다. 따라서 차량 전체 UI가 공식 Figma 키트와 픽셀 단위로 동일하다고 주장하지 않는다. 캐릭터 모션은 실제 Figma 원본과 에뮬레이터를 대조했다.

## 성능 관측

화면 녹화를 포함한 첫 측정에서 A/B의 업데이트 간격은 평균 약 35.2ms, 약 28.4회/초였다. 단일 최대 간격은 각각 44ms·45ms였다. 4초 뒤에는 타임라인이 종료됐으며 반복 애니메이션은 없다.

[메모리 기록](runtime/run-20261109T143534Z/memory-after-playback.txt)은 전체 앱 PSS 86,624KB, 약 84.6MiB를 보였다. [GPU 기록](runtime/run-20261109T143534Z/gfxinfo.txt)은 약 23.11MB의 GPU 캐시, 렌더 프레임 p50 16ms·p95 17ms를 보였다.

같은 gfxinfo에서 새 프레임 deadline 기준의 jank는 84.49%, legacy 기준은 0.66%로 크게 달랐다. 녹화의 영향만으로 설명할 수 있는지 확인하기 위해 [녹화 없는 1회 재생](runtime/run-20261109T143534Z/gfxinfo-unrecorded.txt)을 추가 측정했다. 평균 업데이트 간격 35.53ms·최대 41ms였으며, modern jank 83.08%·legacy 0%·p95 17ms였다. 따라서 녹화만의 현상으로 단정하지 않는다.

[실제 CPU 표본](runtime/run-20261109T143534Z/cpu-during-playback.txt)은 재생 중 프로세스 기준 8·7·7·9·7%였다. 이 짧은 표본을 장시간 사용량으로 일반화하지 않는다. 현재 모션과 안전 동작은 실행되지만 높은 deadline 지연 지표를 성능 통과로 표시하지 않았다. 실제 차량 GPU에서의 프레임 안정성과 장시간 열·메모리 검증은 남아 있다.

## 재현 도구

- [실제 기기 검증](../../../scripts/verify_nunti_motion.py): 설치된 APK, 연결된 Pleos AVD, 준비된 공식 Virtual Console 필요. 차량 상태를 저장하고 `finally`에서 복원한다.
- [픽셀 검증](../../../scripts/verify_nunti_motion_pixels.py): 저장된 실제 Android 프레임과 Figma 프레임을 읽는다.
- [Figma 검증](figma-verify.py): 실제 API readback·파일 해시·타임라인을 검증한다.
- [AVFoundation 프레임 추출](figma-extract-frames.swift): 실제 Figma MP4의 시점별 PNG를 추출한다.

```sh
python3 docs/redesign/birth-motion-v1/figma-verify.py
.worktrees/server/backend/.venv/bin/python scripts/verify_nunti_motion_pixels.py \
  docs/redesign/birth-motion-v1/runtime/run-20261109T143534Z
```

별도 유료 이미지·영상 생성 모델을 호출하지 않았다. 동작 중에는 외부 API, 서버, 스트리밍 영상 또는 신규 이미지 생성이 필요 없다. 테스트 성공은 debug 프로토타입의 결과이며 차량 출시 승인을 뜻하지 않는다.
