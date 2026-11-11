# 독립 Figma 구조 검증

실제 MCP 읽기 결과에 대한 검사 **13/13 PASS**. directions/main/compact/support/flow/options 결과 파일의 최종 화면 36개를 포함한다. 읽기 시각은 2026-11-10 00:44:50 KST다. Compact 화면 수정과 경로 누락 시 두 버튼, Options 네 화면 추가 이후 전체를 다시 읽었다.

| 항목 | 실제 읽기 결과 |
|---|---|
| 화면 | native FRAME 36개. 넓은 창 1682×1210, 좁은 창 830×1210 |
| 레이어 | 1,410개 |
| Auto Layout | 716개 |
| native INSTANCE | 326개 |
| 보이는 TEXT | 588개. 모두 Noto Sans KR |
| 이미지 | 30개. 승인된 눈티 Base/CoastCurious 두 해시만 사용, 원본 각각 768×768 |
| 액션 터치 영역 | Action/Choice/Field와 명시된 액션 인스턴스 모두 가로·세로 76 이상 |
| 미분류 화면 밖 요소 | 0개 |
| 의도된 스크롤 넘침 | compact PRE_TRIP 낮/밤 각 14개. 정차용 수동 스크롤 viewport 내부 |
| Motion | 모든 1,410개 노드의 manual/resolved animation 및 animationStyles 읽기 성공. 실제 모션 0개 |
| 프로토타입 | 42개 모두 ON_CLICK. 시간 기반 자동 전환 없음 |
| DRIVING_RESTRICTED | 낮/밤·넓은/좁은 4개 화면 모두 스크롤·모션·reaction 0개 |

실제 공식 마스터 참조도 남아 있다.

| 마스터 | 의미 | 해당 INSTANCE 수 |
|---|---|---:|
| 18:145 | primary medium enabled button | 30 |
| 18:181 | secondary medium enabled button | 100 |
| 18:153 | primary medium disabled button | 6 |
| 18:318 | entered text field | 42 |
| 18:411 | off switch | 4 |
| 18:467 | selected checkbox | 6 |

switch 80×48와 checkbox 64×64는 시각적 내부 심볼이다. 외부 Motion toggle과 Route confirmation은 높이 80의 터치 영역을 갖는다. 내부 심볼 치수를 액션 터치 영역으로 오판하지 않았다.

MissingRoute 낮/밤 두 화면에 각각 높이 80의 액션 두 개가 있다. Options 네 화면은 각각 830×1210이고 액션 인스턴스 다섯 개, 최소 높이 76을 갖는다. Compact REVEAL 두 화면은 의도된 화면 밖 넘침도 0개다. Compact PRE_TRIP의 수동 스크롤 넘침만 별도 집계했다.

이미지는 UI 화면 전체를 평탄화한 비트맵이 아니다. 두 승인 해시 외 IMAGE fill이 없으며 모든 이미지 노드는 캐릭터 컴포넌트 내부다. 텍스트·버튼·필드 등 UI는 별도 네이티브 레이어로 유지되어 있다.

## 증거와 재현

- [실제 읽기 결과](figma-structure-readback.json): 화면별 치수·유형 수·이미지 노드 ID/해시·글꼴 집계·오류 ID·마스터 참조.
- [검증 결과](figma-structure-verification.json): 13개 검사와 범위 제한.
- [MCP 읽기 템플릿](figma-audit-reader-template.js): 읽기만 수행한다.
- [로컬 검증기](../../../scripts/verify_nunti_figma_ui.py): 결과 파일에서 36개 화면 ID를 수집하고 쿼리를 생성한다.

```sh
python3 scripts/verify_nunti_figma_ui.py --emit-reader /private/tmp/nunti-figma-audit.js
# 생성된 JS를 use_figma로 file LHLHBra8ON3OdVW0qhBnbm, page 15:4에서 실행한다.
# 반환 JSON을 docs/redesign/pleos-ui-v1/figma-structure-readback.json에 저장한다.
python3 scripts/verify_nunti_figma_ui.py --verify
```

이번 실제 읽기는 기존 세션 254188e0-b447-4120-b8aa-d805690cb6ba를 사용했다. 새 세션·Figma 객체 변경·스크린샷 재촬영은 하지 않았다. 최초 반환이 도구의 48KB 제한을 초과해 정상 액션의 개별 목록을 집계치로 줄인 뒤 같은 읽기를 완료했다.

## 해석의 한계

이 검사는 레이어 구조를 검증한다. 시각적 텍스트 겹침·대비·실행 중 조작 결과를 대신하지 않는다. 별도의 Figma 이미지 QA와 에뮬레이터 증거를 함께 확인해야 한다.

실제 D/30 에뮬레이터에서는 Journey service가 ACTIVE/LIVE여도 Pleos의 주행 제한 오버레이가 앱을 가린다. Figma의 DRIVING_RESTRICTED 본문은 플랫폼이 허용하는 상황에 대한 설계 제안이다. 플랫폼 가시성이나 주행 허용 승인으로 해석하지 않는다. [런타임 관측](runtime-verification.md)

