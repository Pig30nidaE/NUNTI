# 목적지와 경로에서 새 동반자가 태어나는 시험본

2026-11-03. 사용자 요구에 따라 고정8개 목록을 기본 진입점에서 내려놓고, **목적지·특성·목적 입력 → 경로 그리기 → 실제 경로 trace → 새 몸체로 morph → 얼굴 등장 → 외형에 맞춘 로컬 TTS → 도착·보관** 흐름을 구현했다.

[직접 시험하기](../../../prototypes/route_birth/TESTING.ko.md) · [실행 파일](../../../prototypes/route_birth/Start%20Route%20Nunti.command) · [최종 Debug APK](../../../.local/route-birth/Nunti-Route-Birth-debug.apk) · [저장 증거 통합 재검사](../../../prototypes/route_birth/delivery-verification.json)

## 실제 생성 방식

입력 경로의 원래 순서를 유지해 길이 기준72점으로 다시 표본화한다. 그 선의 비례·방향·길이·굴곡·조화 성분과 새 여정의 seed로 연속적인72점 외피 윤곽과 색을 계산한다. 이전8몸체·16윤곽을 선택하지 않는다. 목적지 특성·목적의 정의된 키워드는 색감·말투에 반영하며 모든 자유 서술을 이해하는 언어 모델은 아니다. 외형은 그림 생성 AI가 아닌 절차적 기하 생성이며, Android Canvas가 실제 전달받은 좌표를 그린다.

생성 연출은 입력한72점 경로를 따라 그린 뒤 실제 새 윤곽으로 변형한다. 얼굴과 발은 몸체 완성 뒤 나타난다. 원본 경로는 외피 안의 무늬로 남지만 외피 밖 부분은 clip되므로 완성 화면에 경로 전체가 보인다는 뜻은 아니다. 최종 수정 후 중간 장면에 분리된 발이 없는 것을 직접 확인했다.

새 여행은 새 UUID·캐릭터·윤곽·음원 결합을 만든다. 재시도는 같은 입력을 같은 ID로 보내 최초 결정을 보존한다. 같은 ID의 다른 입력은409로 거절한다. ID와 데이터의 독립성은 검사했으며 모든 가능한 결과의 전역적 시각 차이를 보장한 것은 아니다.

Sohee 한 화자에게 실제 생성된 몸체의 길쭉함/둥근 비례·색감·굴곡과 여정의 분위기를 반영한 연기를 지시한다. 새 화자 복제와 Anna API 재현은 하지 않는다. 음원은 로컬 모델이 새로 합성하며, 앱은 동일 characterId/profileId/binding/direction/원문/WAV 해시에 묶인 파일만 기존 단일 큐에서 재생한다.

PC 작업자는 이 Mac의127.0.0.1에만 열린 로컬 연결로 앱과 통신한다. 외부 API·계정·패키지 설치·모델 다운로드는 사용하지 않았다. Android 안에서 모델을 추론하지는 않는다. 새 입력마다 APK를 다시 만들지 않는다. 지도 길 찾기·GPS 경로 수신 대신 사용자가 그린 정규화 선을 받는 시험본이다.

## 새 입력으로 실행한 검증

**5개 여정·15개 WAV는 이번 검증 표본 수다. 앱의 선택지나 생성 상한으로 정한 수가 아니다.** 기존 음원 재사용 없이 새로 합성했다.

| 범위 | 실제 관찰 |
| --- | --- |
| 첫 PC 입력3개 | 속초 영금정·대관령 양떼목장·성수 서울숲으로9WAV 생성,42.58초. 생성 중 health43회 응답·최대15.2ms. [실제 합성](../../../prototypes/route_birth/synthesis-01/synthesis-result.json) |
| 앱의 새 입력 | 북서울꿈의숲과 새 경로를 앱에서 POST했다. `GENERATING → 실제 외형 →4단계 생성 연출 → READY`,약14.2초. 새3WAV,재빌드 없음. [원본 실행](../../../prototypes/route_birth/native-runtime-02/verification.json) |
| 실제 사용자 조작 | 테스트용 submit 명령을 쓰지 않고 목적지·특성·목적의 실제 입력창을 채우고 touch로 선을 그린 뒤 생성 버튼을 눌렀다. 별도 새 여정과3WAV가 생겼고 인사가 완주했다. [직접 입력](../../../prototypes/route_birth/gesture-runtime-01/verification.json), [실제 화면 영상](../../../prototypes/route_birth/gesture-runtime-01/route-birth-real-ui.mp4) |
| 원본·앱 연결 | 5입력→5상이한 실제 윤곽→15새WAV를 해시와 원문·모델revision·음성 방향·캐릭터로 대조했다. 실제 앱에서 서로 다른11클립이 완주했다. 나머지4공통클립은 파일 정합성과 중지/큐 검사 범위이며15개 전체 완주로 확대하지 않는다. [통합 재검사](../../../prototypes/route_birth/delivery-verification.json) |
| 실제 스피커 | 최종 새 아바타의 도착 음성을 인증된 에뮬레이터 스피커 PCM에서 수집했다. 원본과5대역 시간별 에너지 NCC0.9279였다. 마이크·사람 청취·보정된 화자 고유성/음질 합격 판정은 아니다. [실제 출력·최종 복원](../../../prototypes/route_birth/final-native-01/verification.json) |
| 보관·복원 | 검증 공간4건, 실제 UI 입력 공간1건을 보관했다. 프로세스 종료 뒤 같은 정체성·도착·보관을 복원하며 자동 발화와 음성 시험 동의 복원은 없었다. 최종 APK에서도9개 실제 Android 입력/저장 경계 검사를 통과했다. |
| 입력 경계 | 실제 HTTP 잘못된 입력27건·동일 요청 재전송·409충돌·미등록 음원/경로 탈출 거절을 확인했다. 입력 원문 canonical SHA와 내용, 초기→READY의 외형·이름·음성 불변성을 Android에서도 검사한다. [독립 QA](../../../prototypes/route_birth/qa-evidence-01.json) |
| 모델·서버 복구 | 15개 단위 검사,실제 자식 프로세스10개 중단 지점 복구. 정상 PC 서버를 실제 한 번 재시작해5READY응답·15WAV·원본40파일이 동일했고 동일 입력5회가 같은 READY를 반환했다. 모델 호출 횟수는 직접 계수하지 않았다. [재시작](../../../prototypes/route_birth/restart-01/verification.json) |
| 외형·연출 | fixed nonce136경로와 같은 경로40개 새 UUID의 좌표 차이/전체 얼굴 타원 내포 검사. renderer CPU96윤곽·9,696frame, 실제 생성3개 Kotlin 해석 통과. native 완성5체와 수정 후 중간 morph를 직접 열어 얼굴가림·잘림·발부착을 확인했다. [AVATAR QA](../../../android/feature/avatar/reports/route-born-qa.md) |
| 정책·중지 | 실제 P의 Car feed, duplicate 거절 뒤 원래 재생 중지, 재생·대기 동시 중지, Settings로 실제 foreground=false 취소, 차단·복귀 무발화를 확인했다. 새 host에서 직접 D/P 전환은 이번 범위에 없다. [실제 정책](../../../prototypes/route_birth/native-runtime-03/verification.json) |
| 빌드·전달 | 최종 Debug·Release 빌드와 Debug lint 통과. 실행 파일 자체로 PC bridge·설치·MainActivity의 새 화면 진입을 확인했다. 최종 APK에서는 실제 입력·연출·3음원·스피커·보관·복원·9경계를 다시 시험했다. |

## 실패 기록과 바이너리 범위

`http-invalid-01`은 의도적인 서버 정지와 겹친 연결 실패다. `native-runtime-01`은 아바타가 생기기 전에 경계 검사 응답을 기다린 검사기 순서 오류다. `native-runtime-02`는4개 생성/앱수신·8음성 완주·보관/복원까지 통과한 뒤, 실제 background 취소 사유가 `INACTIVE`였으나 검사기가 다른 사유만 예상해 전체 FAIL이다. 이 원본과 raw이벤트는 그대로 보존했다. 같은 APK의 후속 `native-runtime-03`은 실제 취소와 정책을 정확한 사유로 재검증해 PASS했다.

기존 QA APK는 `a1a18e247f1605313d9927ef362af66c4d66e064e135d333710b49277490dc2b`, 최종 전달 APK는 `e96931982da70b2bf2b7dae595c414b63be5e45b1457b791dd0f16420f8b9d8e`다. 차이는 응원 버튼·음성 설명 두 문구와 발 등장 시점이다. 입력·통신·저장·음성 로직은 같다. 최종 APK의 후속 직접 입력과 복원 검사를 앞 표에서 구분했다. [APK·소스 해시](../../../prototypes/route_birth/delivered-apk.json)

## 직접 시험과 남은 범위

[시험 안내](../../../prototypes/route_birth/TESTING.ko.md)를 따라 목적지와 선을 바꿔 계속 새 동반자를 만들 수 있다. 이 Mac의 작업자와 Pleos 에뮬레이터는 실행 상태로 남겨 둔다. 실제 UI로 만든 푸른 동반자 하나를 사용자 공간에 보관했고, 다시 연 화면은 음성 시험이 꺼져 있다. 이전8여정 시험본과 이전 모델/음원/복원 증거는 보존했다.

지도·실제 내비 여정 입력, 자유 서술의 폭넓은 의미 해석, Android 모델 추론, 서버 컬렉션 동기화/동의/삭제, 생성 규칙 버전업 호환, 주행 피드백 연결은 남았다. 실차·새 host 직접 D/P 전환·전역적 시각 유일성·귀여움·소장 의향·음성 자연스러움/외형과의 어울림·운전습관 개선은 이번 수치 검사로 승인하지 않는다.

저장된 실제 증거만 다시 읽으려면 다음을 실행한다. 새 여정을 합성하거나 기기를 조작하지 않는다.

```sh
python3.12 scripts/verify_route_birth_delivery.py
```
