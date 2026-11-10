# 눈티 기본 원화 리파인 A/B

2026-11-09 · 검토용 시안 · 권장 방향 A · 제작 승인 전

기존 눈티 원화를 고정 참조로 사용해 A/B를 실제 생성하고, 각도와 축소 표정을 보정했다. **A의 매트한 입체 표현을 추천한다.** 원화의 둥근 후드, 갈색 눈의 깊이와 따뜻함이 이어지면서 직물 무늬·잔주름이 줄어 얼굴이 먼저 보인다. B는 얇은 윤곽선 덕분에 작은 크기에서 외곽이 더 또렷하다.

## 결과 파일

| 파일 | 내용 | 형식 |
| --- | --- | --- |
| [comparison-board.png](comparison-board.png) | 원본과 A/B, 세 각도, 표정, 축소 샘플을 모은 한 장의 비교 보드 | 2600×2200 PNG |
| [nunti-a-sheet-v3.png](nunti-a-sheet-v3.png) | A 최종 후보 · 정면/3⁄4/측면 + 기본/감정 6종 + 색상 견본 | 1254×1254 RGB PNG |
| [nunti-b-sheet-v4.png](nunti-b-sheet-v4.png) | B 최종 후보 · 같은 구성 | 1254×1254 RGB PNG |
| [small-size-review.png](small-size-review.png) | 전신 H64/H128, 얼굴 64×64, 어두운 배경, 검정 실루엣 | 1200×1050 PNG |
| [nunti-a-front-transparent-v1.png](nunti-a-front-transparent-v1.png) | A 정면 투명 추출 초안 | 1208×1302 RGBA PNG |
| [nunti-b-front-transparent-v1.png](nunti-b-front-transparent-v1.png) | B 정면 투명 추출 초안 | 1086×1448 RGBA PNG |
| [character-bible.md](character-bible.md) | 정체성, 표정, 팔레트, 제작 인계 기준 | 문서 |
| [verification.md](verification.md) | 확인 방법, 판정, 미검증 항목 | 문서 |
| [asset-manifest.json](asset-manifest.json) | 파일 해시, 참조, 프롬프트, 버전, 승인 상태, 알파 정보 | 메타데이터 |

원본은 `docs/design/avatar-v6/assets/nunti-base-character.png`다. 원본과 기존 승인 자산을 교체하지 않았다. 이번 작업은 `docs/redesign/identity-refine-v1/` 안의 시안과 문서에만 기록했다. 앞선 감사 문서와 앱 기능에는 변경을 적용하지 않았다.

각 안에는 기본 표정 외에 **차분함·호기심·걱정·놀람·안도·기쁨**이 있다. 작은 표정의 중복을 줄이기 위해 호기심의 눈썹/시선, B 안도의 입 모양을 최종 보정했다.

## 선택과 다음 단계

A를 기본 마스터 리파인의 방향으로 선택하는 것을 권한다. 선택 후에는 얼굴 기준점과 세 각도 비율을 정밀하게 맞추고, 스카프·가방·배지·표정을 레이어로 분리해 정식 마스터를 만든다. 투명 추출물의 가장자리와 배지 경로선을 정리한 뒤 기존 렌더러에 들어갈 정적 자산으로 검증한다. 이는 다음 단계의 권고이며 이번 작업에서 제작 승인을 대신하지 않는다.

두 시트는 래스터 콘셉트다. 편집 가능한 벡터, 3D 모델, 리깅 완료 파일이 아니다. 투명 PNG는 실제 알파를 갖지만 외곽의 반투명 잔여가 있어 배포 전에 정리가 필요하다. 보드에 보이는 주 비교 이미지는 최종 시트의 실제 크롭이며, 투명 추출물은 별도로 생성한 파생 시안으로 구분했다.

## 생성 기록과 비용

연결된 **내장 image_gen**으로 9회 생성/편집했다. 별도 API 키를 사용하는 유료 API 호출은 **0회**다. 내장 도구의 계정별 크레딧·과금 금액은 제공되지 않아 계산하지 않았다. 외부 유료 API로 전환하지 않았다.

정확한 입력은 [초기 프롬프트](prompts.json), [각도·배지·투명 추출 보정](revision-prompts.json), [최종 표정 보정](final-expression-prompts.json)에 저장했다. 시드와 모델 식별자는 도구에서 제공되지 않았다. 같은 프롬프트로 동일 픽셀을 재생성할 수 있다고 보장하지 않는다. 최종 파일의 SHA-256을 결과 고정 기준으로 사용한다.

## 보드 재생성

[render_boards.py](render_boards.py)는 원본 PNG를 변경하지 않고 HTML 안에 그대로 넣는다. 크롭은 SVG 뷰포트, 실루엣은 표시 필터로 만든다. 이미지 내용을 코드로 보정하지 않았다.

```sh
python3 docs/redesign/identity-refine-v1/render_boards.py
```

브라우저에서 `comparison-board.html`을 2600×2200, `small-size-review.html`을 1200×1050, device scale factor 1로 캡처하면 같은 배치의 PNG를 얻는다. PNG를 100%로 열어 크기를 비교한다. 앱의 자동 축소 미리보기는 실제 64px 표시가 아니다.
