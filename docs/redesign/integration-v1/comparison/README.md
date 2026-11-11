실제 Pleos 앱의 네 상태를 이전 화면 및 승인 Figma와 비교했다. 재촬영한 출발 전·변신 완료·도착 화면에서 캐릭터, 본문, 하단 조작이 잘리지 않는 것을 확인했다. 주행 제한 상태는 현재 기기에서 보이는 시스템 차단 화면을 그대로 사용했다.

- [실제 앱 이전 / 이후](before-after-actual-day.png)
- [승인 Figma / 실제 앱](figma-vs-actual-day.png)
- [승인 기본형 / 실제 앱의 9개 변형](character-runtime-matrix.png)
- [기존 승인 변형 보드](../../route-variants-v1/comparison-board.png)

전체 기기 캡처는 2560 × 1440이며, 실제 앱 영역 `[853, 90, 2535, 1300]`을 1682 × 1210으로 잘랐다. 이 원본 픽셀 크롭은 `app-crops/`에 저장했다. 비교 보드에 배치할 때만 50%로 축소했다. 원본 PNG, 플랫폼 영역, 텍스트, 경로, 점수, 캐릭터 픽셀을 수정하지 않았다. [스크린샷 manifest](manifest.json)에 입력·출력 SHA-256, 크롭 좌표, Figma node, 실제 상태·XML·CarUx 파일의 해시가 있다.

실제 앱의 9개 변형은 보정된 APK의 WebView 캔버스에서 4000ms 최종 상태를 얻은 PNG다. 9개 모두 최종 최적화 APK에서 재검사한 `runtime-endpoints-final` 캡처다. 각 PNG의 768 × 768 RGBA 픽셀이 같은 브라우저에서 디코딩한 저장 이미지와 정확히 일치하는 것을 검사했다. 기본형은 승인된 번들 PNG이며 런타임 캡처와 구분했다. [캐릭터 manifest](character-runtime-manifest.json)에 9개 artifact ID, 원본 이미지 SHA, 입력 출처, 최종 endpoint 보고서 및 픽셀 비교 결과를 기록했다. 원본 A/B 시트와 기존 승인 보드는 수정하지 않았다.

첫 실기 검사에서 발견한 WebView 배율, 네이티브 가변 폰트 굵기, 부제 잘림, 반복 화면 전환의 제목, 남아 있던 안내 배너 문제는 수정 후 다시 확인했다. [첫 검사 기록](initial-visual-review.json)은 수정 전 증거로 남겼다. 최종 이미지에서 네이티브 본문은 읽을 수 있는 굵기로 표시되고, 분할 결과의 ‘여정 옵션 · 이야기’까지 초기 화면에 들어온다. [최종 시각 검토](visual-review.json)에 사용한 추가 야간·분할 캡처와 해시를 기록했다.

Figma와의 차이는 다음과 같다.

- 경로 미리보기는 기존 렌더링 파이프라인의 실제 입력 이미지를 사용한다. Figma의 예시 선을 런타임 경로로 덮어쓰지 않았다.
- 목적지, 이름, 시간, 점수, 평가 범위와 설명은 저장된 실제 데이터를 유지한다. 따라서 Figma 예시와 문구 및 줄바꿈이 다르다.
- 완료된 변신에서는 ‘바로 보기’를 숨긴다. 다시 보기와 모션 축소는 기존 동작에 연결되어 있다.
- 네이티브 넓은 화면의 부제 영역은 120px이다. 72px 제목, 8px 간격, 40px 부제가 108px 영역에서 잘리던 문제를 해결한 값이다.
- Figma의 주행 동반자 화면은 표시 허용을 전제로 한 제안이다. 현재 에뮬레이터에서 관찰한 실제 결과는 Pleos의 시스템 차단이다.

재현 명령은 저장소 루트에서 실행한다. 파일은 로컬 이미지 합성만 수행하며 기기나 API를 조작하지 않는다. 검토 승인 표시가 없는 캡처 맵은 최종 보드 생성을 거부한다.

```sh
python3 scripts/build_nunti_integration_comparison.py \
  --characters-map docs/redesign/integration-v1/comparison/character-capture-map.json
```

비교 보드의 라벨에는 번들 Noto Sans KR을 사용했다. 해당 폰트의 OFL은 `prototypes/avatar_generator/assets/fonts/`에 함께 보관되어 있다. 이 비교 결과는 스크린샷 수준의 시각 검토이며, 주행 표시 자격이나 전체 접근성 검증을 대신하지 않는다.
