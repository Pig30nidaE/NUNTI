# Figma Motion 제작·검증 기록

2026-11-09. 사용자가 지정한 TOZI에 새 파일을 만들고 실제 Figma Motion API로 두 방향을 작성했다. 스토리보드나 영상 생성 모델의 출력이 아니다.

- [Figma 파일](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm)
- [A · 빛길](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=4-13): 스카프 길과 포켓 무늬가 왼쪽부터 드러난다. 길 끝에 반지름 8px 잔광과 3px 중심빛이 짧게 이동한다.
- [B · 잔잔한 색](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=4-56): 길과 포켓 무늬의 투명도를 올린다. 빛과 이동 효과가 없다.

Figma에서 해당 프레임의 Motion 타임라인을 재생하거나 저장한 `figma-a-light-trail-24fps.mp4`, `figma-b-quiet-color-24fps.mp4`를 재생하면 된다. 둘 다 768×768, 24fps다. 타임라인은 4000ms이며 MP4에는 4.0초 끝점 프레임이 포함되어 컨테이너 길이가 4.0417초다. Figma 미리보기의 `loopMode: loop`는 제작 도구의 반복 재생 설정이다. Android는 주차 상태에서 명시적으로 시작하는 1회 재생이며 주행·중단 후 자동 재개하지 않는다.

## 최종 구성

| 항목 | 시간 | A | B |
|---|---:|---|---|
| 같은 눈티 몸체 | 전체 0–4000ms | 승인 A 공통 컴포넌트, 위치·크기·불투명도 고정 | 동일 |
| 스카프의 길 | 450–1300ms | 너비 0.001→55px clip reveal | opacity 0→1 |
| 바다 스카프 색 | 1300–1900ms | opacity 0→1 | 동일 |
| 바다 포켓 무늬 | 1700–2500ms | 너비 0.001→70px clip reveal | opacity 0→1 |
| 얼굴 안쪽 표정 | 2850–3050ms | 기본 표정 1→0, 호기심 0→1 | 동일 |
| 안정 | 3400–4000ms | 최종 상태 유지 | 동일 |

모든 변화의 easing은 `cubic-bezier(.4,0,.2,1)`이다. 표정 단계는 2700–3400ms 안에 있으며 실제 교체를 200ms로 제한했다. 최초 700ms 교체에서 보였던 오래 남는 입 중첩을 실제 영상 프레임 검사 후 줄였다. 3.0초는 아직 교체 도중이므로 아주 약한 국소 혼합이 남고 3.05초 이후 최종 표정으로 고정된다. 몸체나 머리 전체를 교체하거나 용해하지 않는다.

최종 빛 색은 Android와 같은 따뜻한 금색 `RGB(249,216,146)`이다. Figma A의 두 ellipse fill만 이 값으로 맞추고 실제 readback으로 확인했다. 모든 키프레임과 B는 그대로이며 A의 24fps 영상 및 추출 프레임을 새 출력으로 교체했다. Figma stage 배경 `#F6F4EF`와 Android 카드 `#EEF2E7`의 차이는 유지한다. 모션 픽셀 비교는 Android 투명 캡처를 Figma와 같은 배경 위에 합성해 수행한다.

## 증거

- `figma-design-context-a.json`, `figma-design-context-b.json`: 실제 `get_design_context` 응답. 두 호출 모두 스크린샷을 반환했다. 생성된 React 코드는 참조이며 앱 코드는 Kotlin Canvas다.
- `figma-motion-context.json`: 실제 `get_motion_context`의 키프레임 CSS, 타임라인 소유자, 4000ms 길이.
- `figma-manual-tracks.json`: 실제 Plugin API readback. 고정 몸체 인스턴스에 키프레임이 없고 opacity=1, x=y=0임을 확인했다. 이미지 hash와 등록 좌표도 포함한다.
- `figma-assets-and-render.json`: 승인된 공통 PNG의 로컬 SHA256와 Figma imageHash 대응, 프레임 추출의 실제 시간. 이미지 7개를 업로드했으며 새 캐릭터 원화나 영상 모델을 호출하지 않았다.
- `figma-final-resting.png`: Figma 정지 화면. 원본 최종 PNG를 동일 배경에 합성한 이미지와 root 비교에서 최대 채널 차이 2, 채널 MAE 약 `[.006,.013,.016]`의 래스터 반올림 차이만 확인됐다.
- `figma-motion-contact-sheet.png`, `figma-{a,b}-frame-*.png`: 실제 최종 MP4에서 AVFoundation으로 추출한 프레임. 0, 1, 3, 4초는 정확한 프레임이며 2.2초 요청은 24fps의 2.1667초 프레임이다.
- `figma-extract-frames.swift`: 재실행 가능한 로컬 영상 프레임 추출기. macOS sandbox 안에서는 VideoToolbox decode `-11821/-12911` 오류가 있었고 권한이 허용된 실행에서 정상 추출했다.
- `figma-verify.py`, `figma-verification.json`: 저장된 API readback·원본 SHA256·프레임 크기를 검증한다. `python3 docs/redesign/birth-motion-v1/figma-verify.py`로 재실행한다.

## 범위와 확인된 지원

Figma Motion 스타일 탐색, manual keyframe 쓰기·readback, 타임라인 길이 변경, 이미지 업로드, 실제 MP4 export가 모두 성공했다. 초안 5fps 진단 영상은 최종과 혼동하지 않도록 제거했으며 최종 24fps 영상만 남겼다. 외부 유료 이미지·영상 생성 모델 호출은 0회다. Figma 도구는 별도 결제나 크레딧 소비를 표시하지 않았다.

연결된 라이브러리와 검색에서 Pleos 컴포넌트가 없었고, 현재 MCP에는 공식 `.fig` 키트 가져오기를 위한 API가 노출되지 않았다. 따라서 이 파일은 768² 캐릭터 모션 stage만 만들었다. 플랫폼 내비게이션·예약 주행 정보 영역·자동차 UI chrome을 임의로 복제하지 않았다. 차량 전체 화면의 비교, `CarUxRestrictions`, 모션 줄이기, 중단, 성능 검증은 Android 실행 결과와 함께 별도 판단한다.

A의 길을 따라 변화가 진행되는 방식이 원인과 결과를 읽기 쉬워 기본 추천이다. B는 장식광을 원치 않는 상황의 차분한 대안이다. 사용자 선택 전까지 두 방향 모두 제작 프로토타입이며 승인된 production motion으로 표시하지 않는다.
