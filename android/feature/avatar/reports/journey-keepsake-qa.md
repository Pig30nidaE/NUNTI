# 여정 기념 오브젝트 renderer 검사

`journey-keepsake-canvas-1`은 `JourneyVisualSpec.kt`의 검증된 레시피를 `JourneyKeepsake.kt`에서 정적으로 그린다. 공개 모델과 enum은 `docs/design/journey-mvp/implementation-brief.md`를 따른다. 입력 palette는 세 개의 `#RRGGBB`, seed는 소문자 16자리 hex, 비례는 각각 finite `0.75..1.25`다. body마다 registry에 등록된 두 shape만 받는다.

## 소스와 자동 검사

| 항목 | 구현과 확인 범위 |
| --- | --- |
| 8몸체·16shape | 각 shape의 별도 폐곡선. `JourneyBody.shapeIds`가 family·shape 조합을 검증 |
| 비례 | 몸체별 기본 폭·높이에 입력 비례를 적용. 320 viewBox 안의 260×247 범위로 균등 축소하고 바닥을 유지 |
| 목적 | registry의 색과 배치에 따라 하단·중앙·비대칭 코어 빛을 그림. EXHIBITION은 두 광원 |
| 모티브 | 꽃잎·진주 거품·안개층·씨앗 잎·잔물결·창문 조각·점의 7종 |
| 경로 무늬 | 파도·등고선·격자·가지·굽이·긴 평행선·교대 경로·짧은 평행선·점의 9종 |
| seed | 시간이나 mutable RNG 없이 네 고정 채널이 하이라이트 길이, 얼굴 기울기, 모티브 위치·각도, 경로 높이를 결정 |
| 재질·얼굴 | 접촉 그림자, 뒤쪽 외피, 내부 광원·모티브, 굴절 띠, 앞쪽 윤곽, 불투명 크림 얼굴 순으로 그림. 6종 Emotion 분기 |
| 표시 정책 | visible=false면 Canvas·layout·semantics 생성 전 return. interactionsAllowed=false면 외형 고정·중립 표정·설명 "눈티"만 제공 |
| 정적 성능 | geometry·Path·palette를 remember로 보존. outline은 4~6개 cubic, 루프는 고정 개수. animation clock·외부 이미지·API 호출 없음 |

CPU 검사는 실제 Compose가 사용하는 cubic outline을 표본화한다. 16개 폐곡선의 상호 구별, finite 좌표와 경계, 400개 비례 배치, 각 배치의 얼굴 타원 48점이 실루엣 안에 있는지 검사했다. 잘못된 ID·seed·shape 조합·색·색 개수·NaN·무한대·범위 밖 비례를 거부하는지 확인했다. 입력 팔레트 변경의 격리와 seed 결정성, 비례가 실제 종횡비를 바꾸는지도 통과했다.

```sh
JAVA_HOME=/path/to/jdk-21 \
KOTLINC=/path/to/kotlinc-2.2.21/bin/kotlinc \
bash android/feature/avatar/scripts/test-journey-visual.sh
```

새 파일을 포함한 전체 AVATAR Compose 소스도 로컬의 Kotlin 2.2.21·Compose 1.8.3·Android 35·android.car 실제 바이너리로 컴파일했다. 이 컴파일은 APK·장치 실행 검증과 별개다. 새 클래스는 기존 AvatarSpec·RenderPolicy·공통 Gradle·앱을 수정하지 않는다.

## PM이 실제 앱에서 확인할 항목

1. 번들의 8개 실제 여정을 선택해 characterId와 화면·음성 바인딩이 맞는지 확인한다. 몸체가 이름이나 색만 다른 oval로 보이지 않는지 비교한다.
2. 밝은 크림 배경과 어두운 배경에서 외피 가장자리·그림자·내부 층·불투명 얼굴이 분리되는지 확인한다. 이미지 C의 방향을 따른 Canvas 해석이며 원본 이미지와 동일한 품질이라고 판정하지 않는다.
3. 64px·128px에서 눈 두 개·입·전체 실루엣이 읽히는지 확인한다. 모티브가 얼굴보다 강하거나 눈이 검은 한 덩어리로 뭉치면 실패로 기록한다.
4. NEUTRAL·RELAXED·JOYFUL·STARTLED·CONCERNED·RELIEVED를 같은 characterId로 비교한다. 외형·광원·내부 배치가 바뀌지 않고 눈썹·눈·입·홍조만 바뀌는지 확인한다.
5. visible=false에서 캐릭터 픽셀과 접근성 node·description이 없어지는지 실제 semantics tree로 확인한다. CPU 검사를 접근성 instrumentation 통과로 기록하지 않는다.
6. 같은 spec을 재표시·reroute·재시도·앱 재시작한 뒤 이미지가 유지되는지 확인한다. 동일 geometry의 결정성 검사만으로 host 저장 복원을 완료 처리하지 않는다.
7. 이동·배경 전환, 누락·변조 음원 거절, 도착 저장·복원과 자동 발화 방지는 기존 policy·큐·host 경로에서 확인한다. renderer는 TTS를 호출하지 않는다.

CPU 검사는 렌더러의 geometry와 입력 경계를 검증한다. 실제 썸네일·색·반투명 표현·귀여움·소장 욕구·frame time·음성·운영 접근성의 품질 판정은 자동 검사 결과에 포함하지 않는다.
