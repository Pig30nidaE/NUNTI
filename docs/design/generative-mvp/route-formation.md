# 경로가 몸체가 되는 탄생 연출

2026-11-03. 기존의 경로 표시 후 중앙 원형 마스크로 이미지를 공개하는 방식을 교체했다. 같은 순서의 경로 점이 일곱 번 감기는 리본으로 변형되고, 그 리본이 지나간 부분에서 원본 이미지가 나타난다.

## 비교와 선택

[로컬 비교 시안](../../../prototypes/route_formation/README.ko.md)을 같은 시간축에서 확인했다.

| 시안 | 연결 방식 | 판단 |
|---|---|---|
| A, 리본 | 입력 경로를 같은 점 순서로 감아 몸체를 만들고, 그 붓으로 표면을 칠함 | 선을 몸체의 재료로 쓰는 관계가 가장 잘 보여 채택 |
| B, 윤곽 | 경로가 실제 알파 외곽선으로 변한 뒤 안쪽에 색이 차오름 | 윤곽 연결은 분명하지만 표면 형성이 평면적으로 보임 |
| C, 입자 | 경로를 흐르던 입자가 이미지 안으로 모임 | 원래 경로와 입자 응집이 따로 보이는 구간이 있음 |

Superdesign CLI 실행은 사용자가 허용했지만, 로그인은 사용자가 보류했다. 외부 디자인 생성 없이 로컬 Canvas 시안을 비교하고 Android Compose에 구현했다. 시안 세 개는 탄생 연출의 대안이며 캐릭터 카탈로그가 아니다.

## 구현

- 실제 경로를 누적 길이 기준으로 384점에 다시 배치한다. 같은 점과 같은 펜끝을 연속 이동시켜, 선을 지운 뒤 별도 물체를 표시하는 전환을 없앴다.
- 준비된 원본 RGBA의 알파를 최대 192px로 한 번 분석한다. 실제 행별 폭과 높이에 맞춰 일곱 회전의 리본을 만든다. 고정된 몸체 모양은 사용하지 않는다.
- 리본의 붓 마스크와 마지막 잔여 마스크를 합친 뒤 원본을 `SrcIn`으로 한 번만 그린다. 원본의 부분 투명도가 중복 합성되지 않는다.
- 실제 Android에서 형성 초반의 가로 빈틈을 확인했다. 최소 붓 폭을 실제 몸체 높이와 리본 간격의 1.2배로 보정해 표면이 이어지도록 했다. 밝은 리본의 앞뒤 표현은 유지했다.
- 원본 파일·얼굴·색·비율과 음성 바인딩은 변경하지 않았다. 몸체 전체의 작은 착지·호흡·기울기를 사용한다.

새 탄생은 진행값 0에서 시작한다. 이미지 기하가 준비됐다는 콜백을 받은 뒤 6.9초 연출을 시작하므로, 비동기 계산이 늦어도 중간 모양으로 건너뛰지 않는다. 복원 화면은 완성 상태로 표시하며 탄생이나 발화를 자동 재시작하지 않는다. 차량·화면 표시 허가가 없어지면 연출을 숨긴다.

## 검증

- [기하·알파 회귀](../../../android/feature/avatar/reports/generated-companion-tests.txt): 준비 조합 4,004개, 경로 세 종류, 알파 폭 두 종류, 가로·세로 형상, 연속 펜끝, 리본 간격 대비 붓 폭, 최종 마스크·부분 알파 확인.
- Android debug·release·lint 통과. 최종 빌드 원본은 `.local/generative-mvp/formation-refined-build.log`에 있다.
- 실제 터치로 굽은 경로 일곱 점을 입력하고 서버 입력 일치·연출 완료·인사 재생을 확인했다. 해당 실행은 `.local/generative-mvp/touch-20261102-190643/verification.json`이다.
- 최종 회귀는 **녹화·녹음·스크린샷 저장 없이** 실행했다. `.local/generative-mvp/native-20261103-100544/verification.json`에서 준비 콜백 진행값 0과 연출 시작 순서, 실제 PNG/WAV 해시, 후속 대사·중지·백그라운드 취소·소장품 복원·Android 경계 열 개를 확인했다.
- APK와 설치 파일·소스 해시·기존 서버 검사 근거의 최종 대조는 [verification.json](verification.json)에 기록한다.

최종 [기하 검사](evidence/formation/geometry-tests.txt), [빌드 로그](evidence/formation/build.log), [녹화 없는 실제 앱 검사](evidence/formation/native-verification.json), [실제 이벤트](evidence/formation/native-events.jsonl)의 원본 사본과 [해시 목록](evidence/formation/manifest.json)을 보존했다.

검증 APK는 `.local/generative-mvp/Nunti-Generative-MVP-debug.apk`이며 SHA256은 `f3ec4fe32d4df9bbe33c10bcb09f1589b1b9a3e190ba58062c0131cf99a6f2d0`이다. 실제 API로 새 이미지·음색을 생성하거나 사람의 귀여움·자연스러움을 승인한 검사는 아니다.

## 직접 확인

```sh
cd /Users/pig30nidae/NUNTI
python3 scripts/run_generative_mvp.py
```

앱에서 목적지와 경로를 입력하고 **동반자 만나기**를 누른다. 현재는 샘플 미디어 모드다. [시험 안내](TESTING.ko.md)의 듣기·보관·복원도 이어서 확인할 수 있다.

사용자 지시에 따라 동영상 녹화와 스피커 녹음은 명시적으로 요청받은 경우에만 실행한다.
