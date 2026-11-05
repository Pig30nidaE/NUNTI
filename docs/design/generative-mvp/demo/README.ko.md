# 실제 Android 시연 영상

아래 영상은 탄생 연출 수정 전 최초 연결 시험의 기록이다. 현재 앱의 경로 리본 연출과 최종 검증은 [후속 연출 보고](../route-formation.md)를 따른다.

2026-11-03. [약 32초 시연 영상](nunti-generative-mvp.mp4)은 실행 중인 Pleos 앱의 화면과 같은 실행의 에뮬레이터 speaker 녹음이다. 기존 PNG·Sohee WAV를 사용하는 `OFFLINE_FIXTURE` 모드이며, 새 이미지·음색을 생성한 영상은 아니다. 공급자 API 호출은 0회다.

| 영상 구간, 근삿값 | 확인한 동작 |
|---|---|
| 0–8초 | 입력한 Seoul·River·Rest, 실제 경로 터치, 동반자 만나기 버튼 |
| 8–13초 | 경로 추적→빛→이미지 공개 |
| 13–18초 | 완성 이미지의 전체 움직임, 음성 시험 확인·인사 듣기 버튼 |
| 18–27초 | 기존 인사 음원 재생·완료 |
| 27–32초 | 준비 화면 유지 |

실제 입력 44점이 서버 canonical input에 전달됐고, 앱에서 해당 clip의 `QUEUED→STARTED→COMPLETED`를 확인했다. 이 판정과 speaker 신호는 [실행 원본](../../../../.local/generative-mvp/touch-20261102-182419/verification.json)에 있다. 귀여움·한국어 자연스러움·실제 API의 품질 승인은 수행하지 않았다.

[영상 검증 JSON](nunti-generative-mvp.verification.json)은 영상 압축 sample 1,888개의 SHA와 시각이 원본과 같고, 출력에 영상 1 track과 AAC 음성 1 track이 있음을 기록한다. 음성은 해당 실행의 실제 speaker PCM이다. 원본 packet 사이의 시간 공백에 무음을 채웠으며 음높이·속도·화자는 변경하지 않았다. 음성 시각 정렬은 packet 시각과 녹화 시작 명령 시각을 사용한 근삿값이다. 가청 지연 측정에 사용하지 않는다.

MP4 SHA256은 `f90fce5e8318206b87165e8b26116f48574b8de95d7b3311e4d7209356d7ef63`, 크기는 11,313,410 byte다. 재녹화·내보내기는 [시험 안내](../TESTING.ko.md), 실제 생성 계정 연결은 [API 키 설정](../API-SETUP.ko.md)을 따른다.
