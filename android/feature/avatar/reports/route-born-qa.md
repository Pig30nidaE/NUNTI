# 실제 경로에서 태어나는 눈티 renderer

2026-11-03. `RouteBornSpec.kt`와 `RouteBornCompanion.kt`는 PC가 제공한 72개 outline점과 72개 route점을 사용한다. 기존 JourneyKeepsake와 16개 실루엣 파일은 변경하지 않았다. 새 코드는 bodyFamily·shapeId·몸체 후보 목록을 사용하지 않는다.

## 공개 API

```kotlin
data class RouteBornPoint(val x: Float, val y: Float)
data class RouteBornFace(val cx: Float, val cy: Float, val scale: Float, val eyeSpacing: Float)
class RouteBornSpec(
    characterId: String,
    outline: List<RouteBornPoint>,
    route: List<RouteBornPoint>,
    palette: List<String>,
    face: RouteBornFace,
)
@Composable
fun RouteBornCompanion(
    spec: RouteBornSpec,
    progress: Float,
    emotion: Emotion = Emotion.NEUTRAL,
    modifier: Modifier = Modifier,
)
```

package는 `ai.nunti.avatar`다. spec은 세 입력 목록을 복사하고 수정할 수 없는 목록으로 보관한다. identity는 `route-` 뒤 소문자 hex 24자리다. outline은 정확히 72점과 `.05.. .95`, route는 정확히 72점과 `0..1`, palette는 세 개의 `#RRGGBB`다. 좌표는 finite여야 한다. 비퇴화·비교차 shell과 길이 0이 아닌 경로를 검증한다.

face는 cx=.5, cy=.43, scale=.8..1.1, eyeSpacing=.85..1.15다. 실제 얼굴 타원 반경은 normalized `rx=.22*scale`, `ry=.145*scale`다. 타원의 중심이 polygon 안에 있고, 타원 좌표로 변환한 모든 polygon 변이 unit disk 안으로 들어오지 않는지 해석적으로 검사한다. 외형 안의 몇 개 표본점만 확인하는 검사보다 강한 경계 검사다.

## 연출과 geometry

| progress | 실제 동작 |
| --- | --- |
| 0.. .35 | 실제 route를 누적 길이 기준으로 그림. 입력점의 순서와 실제 선분을 유지하고 끝에 작은 빛을 표시 |
| .35.. .8 | 72개 actual route점 각각이 같은 index의 actual outline점으로 이동. smoothstep 보간, 두 끝 사이의 폐합 선분도 점차 나타남. 재질은 뒤쪽부터 생김 |
| .8..1 | 72개 outline을 그대로 유지하며 진주빛·내부 route·얼굴·발 등장. 1은 정적 완성 캐릭터 |

모든 좌표는 320 viewBox의 동일한 domain rectangle, left=24, top=12, width=272, height=272를 사용한다. 외부 Canvas는 작은 변을 기준으로 균등 scale하고 중앙에 배치한다. 외형점을 다시 정렬하거나 preset으로 교체하거나 spline으로 점을 바꾸지 않는다.

완성 재질은 접촉 그림자, 뒤쪽 외피, 반투명 외피, 낮은 내부 광원, 상단 넓은 광택, 실제 route, route 표본 위치의 작은 진주, 굴절과 윤곽, 불투명 얼굴 순서다. 발은 bounding box의 바닥이 아니라 각 발 x에서 actual polygon의 하단 교차점에 붙인다. 6개 Emotion을 지원하며 RELAXED는 반쯤 뜬 눈, RELIEVED는 감은 눈과 홍조로 구분했다.

완성물의 내부 route는 입력 좌표 그대로 shell에 clip한다. shell 밖에 있는 부분과 불투명 얼굴 뒤의 부분은 가려진다. 전체 원본 route는 앞 trace 단계에 보인다. 원본 route를 몸체 안에 작게 재배치하거나 실제 도로·GPS 경로라고 해석하지 않는다.

renderer는 자체 timer·coroutine·무한 애니메이션·모델·네트워크·음성을 실행하지 않는다. host가 progress와 차단·foreground·차량 정책을 소유하며, 차단 시 이 Composable 전체를 제거해야 한다. 이 API에는 RenderState가 없으므로 renderer만으로 차량 정책 검증을 완료할 수 없다.

## CPU 검사와 설계 스케치

```sh
JAVA_HOME=/path/to/jdk-21 \
KOTLINC=/path/to/kotlinc-2.2.21/bin/kotlinc \
bash android/feature/avatar/scripts/test-route-born.sh
```

최종 CPU 실행은 exit 0이다. `.local/route-born-avatar/cpu-tests.log`에 출력을 보존했다.

- fixture가 계산한 서로 다른 96개 연속 polygon을 그대로 보존했다. 이는 PC의 실제 여정 샘플이 아닌 geometry 검사 입력이다.
- 9,696개 frame에서 결정성, normalized 경계, 정확한 route·outline 종료점, .35와 .8 경계의 연속성, reveal 범위를 확인했다.
- 불균등 선분과 길이 0인 중간 선분이 있는 route에서 누적 길이 기준 trace를 확인했다.
- 점 개수·NaN·범위 밖 좌표·영 경로·중복 변·교차 shell·타원 침범·face·palette·progress 오류를 거부했다. caller의 원본 목록 변경은 spec에 영향을 주지 않았다.
- 96개 polygon의 양발 위치에서 실제 하단 교차값을 확인했다.

같은 polygon과 route로 A clear line, B satin volume, C pearl keepsake의 Java2D 설계 스케치 세 개를 만들어 `.local/route-born-avatar/design-variants.png`를 직접 열어 비교했다. A는 밝은 배경에서 외곽이 약하고 B는 내부 route가 평면 무광처럼 읽혔다. C의 밝은 외곽과 하단 확산 빛을 Compose의 재질 방향으로 선택했다. 이 스케치는 설계 비교이며 실제 Compose 픽셀 검증 증거가 아니다.

PC의 실제 `prototypes/route_birth/synthesis-01/case-{1,2,3}-ready.json`도 읽었다. 해당 visual의 모든 점·색·face를 공개 생성자에 그대로 넣는 별도 Kotlin CPU 실행이 exit 0으로 통과했다. 세 실제 artifact가 동결된 spec의 해석적 face 내포 검사를 통과하고, 공급된 outline 세 개가 서로 다름을 확인했다. 입력 파일 SHA-256은 `.local/route-born-avatar/actual-artifact-inputs.json`, typed 검사 입력은 `ActualArtifacts.kt`, 결과는 `actual-artifact-check.log`에 남겼다. 아직 실제 화면을 관찰한 결과는 아니다.

## Native 화면의 후속 직접 관찰

PM이 실행·수집한 다음 PNG 다섯 장을 AVATAR가 직접 열어 확인했다. renderer를 수정하기 전의 완성 화면 네 장과 cached animation 중간 화면 한 장이다. 새 촬영이나 에뮬레이터 조작은 하지 않았다. 원본 SHA-256은 `.local/route-born-avatar/native-review.json`에 남겼다.

| 실제 캡처 | 관찰 |
| --- | --- |
| `prototypes/route_birth/native-runtime-02/screenshots/case-0-complete.png` | 따뜻한 분홍 외피의 비대칭 몸체다. 상단의 작은 어깨와 왼쪽의 굴곡, 하단의 기울기가 보인다. 내부 경로가 크림 얼굴 뒤로 가려지며 눈·입을 가리지 않는다. 두 발이 외피 하단에 접해 보이고 몸체·그림자의 화면 잘림은 관찰되지 않았다 |
| 같은 폴더 `case-1-complete.png` | 푸른색의 넓고 둥근 몸체와 오른쪽 아래로 내려온 외형이 구분된다. 입력 경로의 꺾인 선이 얼굴 뒤와 하단에서 보인다. 불투명 얼굴의 두 눈·미소·홍조가 읽히고 발이 외피에 붙어 보인다 |
| 같은 폴더 `case-2-complete.png` | 금빛의 세로로 긴 비대칭 몸체다. 좌우 볼륨과 하단 기울기가 앞 두 케이스와 다르다. 원래 지그재그 경로의 일부가 위·아래에서 보이고 얼굴은 가려지지 않는다. 발과 그림자가 화면 안에 있다 |
| 같은 폴더 `case-3-complete.png` | case 0과 같은 분홍 계열이지만 위쪽 어깨·왼쪽 윤곽·하단 기울기가 다르다. 두 눈·입과 얼굴 경계가 외피 안에 남아 있다. 큰 환형 입력 경로의 대부분은 shell clip 밖이어서 완성물에서는 하단 일부만 보인다 |
| `prototypes/route_birth/native-runtime-03/screenshots/cached-animation-900ms-into-route-to-body.png` | 열린 경로의 가지·끝점 빛과, 닫히는 중인 작은 윤곽·옅은 재질이 함께 보인다. 얼굴은 아직 없다. 완성 캐릭터를 즉시 교체한 정지 화면과는 구분되는 경로→외형의 중간 상태로 읽힌다. 이 프레임에서는 옅은 두 발이 아직 작은 본체보다 아래에 떨어져 보이는 문제가 관찰됐다 |

이 관찰로 네 실제 화면의 외형 차이, 완성 상태의 얼굴 가림 없음·발 부착·화면 잘림 없음, 경로를 남기는 재질 표현을 확인했다. 전체 원본 경로를 완성 외형만 보고 복원할 수 있다는 뜻은 아니다. 일부 경로는 외피·얼굴에 가려진다. 중간 화면 한 장으로 시간적 연속성·정확한 72개 점의 대응·frame time까지 독립 검증할 수도 없다. 해당 항목은 CPU·artifact 검사와 host의 실행 기록을 함께 보아야 한다.

case 0은 외형이 완성됐지만 UI가 음성 준비 중임을 표시한다. 이 파일 이름의 complete를 TTS까지 준비됐다는 증거로 사용하지 않는다. 기존 8개 Journey MVP의 썸네일·표정 관찰도 이 새 renderer의 64px·128px 또는 모든 표정 검증으로 재사용하지 않는다.

## 중간 발 분리의 승인된 최소 수정

PM은 위 중간 화면을 검토한 뒤 발의 등장 구간만 바꾸도록 승인했다. `RouteBornCompanion.kt`의 발 draw guard와 두 색 alpha를 `shellOpacity`에서 `frame.faceReveal`로 바꿨다. 실제 polygon 하단 교차점에 붙는 발 위치·크기는 유지했다. 경로→몸체 구간에는 발이 전혀 그려지지 않고, 얼굴이 드러나는 마지막 구간에만 함께 나타난다.

수정 후 요청된 CPU 검사 한 회가 exit 0으로 통과했다. 96개 외형·9,696개 frame과 기존 경계·원본점·trace·타원·양발 위치 검사를 포함한다. `.local/route-born-avatar/cpu-tests-foot-reveal.log`에 기록했다. 소스 변경은 이 블록뿐임을 역치환 SHA-256 검사로 확인했고, 증거는 `foot-reveal-change.json`이다.

- 변경 전 renderer SHA-256 `d29451528ce7e9f9314578feafd248b746a0ca0965b24929e658e8051e7542b7`.
- 재동결 renderer SHA-256 `61d118cbc0cfbf361d1d9875569aeebb8a4d52efb48c92043a5016a8f7d2af34`.
- spec은 변경하지 않았으며 SHA-256 `9b6f789d1c90870f257fab658570e4f418577d5e011ce2e7197fd8f1d9b8aa53`을 유지한다.

위 native PNG 다섯 장은 수정 전 실행 증거다. 수정 직후에는 새 APK의 추가 확인이 남아 있었으며, 다음 두 캡처로 그 범위를 갱신했다. 이 기록은 C 재질 방향의 실제 출력을 관찰한 것이며, 귀여움·소장 욕구를 사람이 승인했다는 뜻은 아니다.

## 최종 APK에서 발 등장 수정 후 관찰

PM은 최종 APK `e9693198…`에서 텍스트 필드·touch 경로·생성 버튼을 사용하는 다섯 번째 새 입력 흐름과 새 WAV 세 개·실제 인사 재생 완주를 확인했다고 보고했다. AVATAR는 그 실행을 재현하거나 청취하지 않았고, 다음 두 실제 PNG를 직접 열어 시각 범위를 검토했다. renderer SHA-256은 재동결한 `61d118cbc0cfbf361d1d9875569aeebb8a4d52efb48c92043a5016a8f7d2af34`와 일치했다.

- `prototypes/route_birth/gesture-runtime-01/mid-route-to-body.png`에서 입력칸의 새 꺾인 경로와, 생성 영역의 교차·폐합 중인 푸른 선·옅은 재질이 함께 보인다. 중간 생성 영역에는 얼굴과 발이 보이지 않는다. 이전 캡처에서 본체 아래에 분리돼 보이던 두 발도 없다. 접촉 그림자는 남아 있지만 발 모양의 타원과는 구분된다.
- 같은 폴더의 `greeting-completed.png`에서 푸른 비대칭 외형과 불투명 크림 얼굴, 내부 실제 경로의 일부, 하단의 굴절 빛이 나타난다. 두 발은 외피 하단에 붙어 보이며, 눈·입의 가림이나 화면 경계의 잘림은 관찰되지 않았다. UI에는 "다 들었어요."가 보인다. 이 문구를 인간 청취나 음질 평가의 증거로 사용하지 않는다.

따라서 이 최종 실행의 두 관찰 프레임에서는 중간 발 숨김과 완성 후 발 부착이 의도대로 보인다. 전체 animation의 모든 frame, 가청 품질, 입력 자동화의 실제 touch 전달 자체는 이 시각 검토의 증명 범위 밖이다. 두 원본 이미지의 SHA-256과 관찰 범위는 `.local/route-born-avatar/native-review.json`의 `postCorrectionReview`에 추가했다. production 소스는 변경하지 않았다.

## 실제 앱에서 남은 확인

PM이 Android 빌드와 실행을 맡았으며 위 화면 범위는 AVATAR가 추가로 읽기 검토했다. AVATAR는 Gradle·모델을 실행하지 않았다. 양 배경의 얼굴·재질·잘림, 64px·128px, 전환 중의 frame time, 실제 접근성 node, policy 차단·재시작·TTS 연결을 CPU나 단일 화면의 통과로 대신하지 않는다.

서로 다른 모든 여정의 외형이 수학적으로 항상 다르다는 보장도 하지 않는다. 실제 새 입력의 geometry 차이와 동일 요청 재시도·복원의 identity 보존은 PC와 host, 독립 QA에서 확인해야 한다. 귀여움·소장 욕구·자연스러운 음성의 평가는 사람의 검토로 남는다.
