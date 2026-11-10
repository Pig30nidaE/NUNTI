# Pleos UI 제안 토큰과 대비 검증

이 표는 Figma foundation snapshot에서 자동 생성했다. 디자인 제안이며 현재 Kotlin token class나 API가 이미 존재한다는 뜻이 아니다. production 코드와 Figma 변수는 이 스크립트가 수정하지 않는다.

## 색상

| Semantic role | Day | Night | 기존 CSS 이름 또는 제안 연결 |
|---|---|---|---|
| `background` | `#F4F3EE` | `#131D1B` | `--bg` |
| `surface` | `#FFFEF9` | `#1D2C28` | `--paper` |
| `soft` | `#E8EDE3` | `#263B33` | `--mint` |
| `tint` | `#E1EAD8` | `#314B3F` | `--surface-tint` |
| `ink` | `#253E3E` | `#EAF2E6` | `--ink` |
| `muted` | `#56675E` | `#B2C4B9` | `--muted` |
| `border` | `#CCD6C9` | `#4D6357` | `--line` |
| `accent` | `#355C4B` | `#B6D0A0` | `--green` |
| `onAccent` | `#FFFFFF` | `#17271F` | `--on-accent` |
| `warm` | `#925238` | `#F1BC8A` | `--accent` |
| `info` | `#2E5C71` | `#9CC7D8` | `--info` |

## 실제 대비 결과

텍스트 42/42쌍은 일반 텍스트 기준 4.5:1, 활성 버튼·focus 후보 8/8쌍은 3:1을 통과했다. 전체 필수 검사 결과는 `PASS`다.
최저 텍스트 조합은 Day `muted` on `tint`의 **4.8499:1**이다. 합격 판정에는 반올림 전 값을 사용한다.

| 모드 | 텍스트 | surface | background | soft | tint |
|---|---|---:|---:|---:|---:|
| Day | `ink` | 11.32 | 10.29 | 9.61 | 9.23 |
| Day | `muted` | 5.95 | 5.40 | 5.05 | 4.85 |
| Day | `accent` | 7.47 | 6.79 | 6.34 | 6.09 |
| Day | `warm` | 5.97 | 5.42 | 5.06 | 4.87 |
| Day | `info` | 7.21 | 6.55 | 6.12 | 5.88 |
| Night | `ink` | 12.71 | 15.04 | 10.45 | 8.30 |
| Night | `muted` | 7.96 | 9.42 | 6.54 | 5.20 |
| Night | `accent` | 8.67 | 10.27 | 7.13 | 5.67 |
| Night | `warm` | 8.52 | 10.09 | 7.01 | 5.57 |
| Night | `info` | 8.02 | 9.49 | 6.59 | 5.24 |

Day 활성 버튼의 `onAccent` on `accent`는 7.5435:1이다.

Night 활성 버튼의 `onAccent` on `accent`는 9.2979:1이다.

`border`는 양 모드 모두 3:1에 미달하는 조합이 있으므로 장식용 구분선으로만 사용한다. 입력 컨트롤을 알아볼 유일한 테두리, focus, 선택 표시, 본문 글자로 쓰지 않는다. 필요한 상태 표시는 충분한 대비의 `accent`와 텍스트 또는 아이콘으로 표현한다. `soft/tint` 배경 차이만으로 선택이나 오류를 알리지 않는다.

일반 텍스트와 큰 글자의 기준은 [WCAG 2.2 대비 설명](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)을 확인했다. 이 검사는 큰 글자 예외를 적용하지 않고 모든 제안 텍스트에 4.5:1을 적용한다. 의미를 전달하는 컨트롤·focus와 장식 구분선의 차이는 [WCAG 비텍스트 대비 설명](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)을 따른다.

## 타이포그래피

글꼴은 `Noto Sans KR`다. 아래 숫자는 Figma 설계 단위이며 Android의 실제 sp 렌더링과 글자 확대는 별도 확인한다.

| Style | 크기 | 행 높이 | 굵기 | 행 높이/크기 |
|---|---:|---:|---|---:|
| Display | 56 | 72 | Bold | 1.29 |
| Title | 38 | 52 | Bold | 1.37 |
| Heading | 30 | 44 | Medium | 1.47 |
| Body | 26 | 40 | Regular | 1.54 |
| Label | 26 | 38 | Medium | 1.46 |
| Caption | 22 | 34 | Regular | 1.55 |
| Number | 72 | 88 | Bold | 1.22 |

일반 문구는 22~56 범위다. Caption도 22로 유지한다.
`Number` 72는 점수 등 짧은 숫자를 위한 별도 예외다. 본문 또는 긴 안내문에 사용하지 않는다.

## 간격·모서리·컨트롤

| Token | 값 |
|---|---:|
| `space/8` | 8 |
| `space/12` | 12 |
| `space/16` | 16 |
| `space/24` | 24 |
| `space/32` | 32 |
| `space/40` | 40 |
| `space/48` | 48 |
| `space/64` | 64 |
| `radius/12` | 12 |
| `radius/20` | 20 |
| `radius/28` | 28 |
| `radius/pill` | 999 |
| `control/height` | 80 |
| `control/compact` | 76 |

간격은 8, 12, 16, 24, 32, 40, 48, 64이다. 12를 포함하는 4단위 배수 체계이며 모든 값을 8단위 격자라고 설명하지 않는다.
기본 버튼 높이 80, compact 높이 76를 제안한다. 창이 좁다고 버튼이나 글자를 임의 축소하기보다 여백과 부가 정보 배치를 조정한다. 실제 hit area, 글자 확대, 다중 창과 공식 Pleos component 규격을 함께 검증해야 한다.

## 재현

```sh
python3 scripts/verify_nunti_ui_tokens.py
```

입력은 `figma-state.json`, 결과는 `token-contrast.json`과 이 문서다. script는 네트워크나 이미지 생성 없이 저장된 HEX 색상의 sRGB 상대 휘도를 계산한다. 필수 텍스트·활성 버튼 검사 실패 시 결과 파일을 남기고 exit code 1을 반환한다.

검사 입력 SHA256: `6e842e52911ddfe95c310a815e5c2d8a525ec639256514f7200937d50eee277a`.

실제 노드의 variable binding, opacity, gradient, disabled 상태, 이미지 위 글자, 글꼴 가장자리와 차량 화면의 가독성은 이 숫자 검사에 포함되지 않는다. 최종 Figma screenshot과 emulator 비교가 필요하다.
