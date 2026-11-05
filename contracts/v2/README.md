# Character generation v2

이 계약은 새 여정에서 생성한 캐릭터와 이후 같은 목소리로 만든 대사를 다룬다. v1 여행 기록 계약과 저장소는 유지한다. 초기 시험의 최종 캐릭터 수는 20개이며, 이후 제품의 카탈로그 크기를 의미하지 않는다.

모든 경로는 기존 서버 Owner bearer 인증과 `data/meta` 응답을 사용한다. 미디어 GET도 인증이 필요하다. 공급자 API 키는 서버 환경변수만 사용한다.

| 경로 | 용도 |
|---|---|
| `POST /v2/character-generations` | 목적지·목적·정규화한 경로와 새 UUID로 작업 제출 |
| `GET /v2/jobs/{requestId}` | 생성 또는 후속 대사 작업 조회 |
| `GET /v2/characters/{characterId}` | 최종 불변 캐릭터 조회 |
| `POST /v2/characters/{characterId}/speech` | `{requestId,text}`로 같은 voiceId의 후속 대사 준비 |
| `GET /v2/assets/{sha256}` | 검증한 PNG/WAV 원본 bytes |
| `GET /v2/generation-capabilities` | 실행 모드, 시험 상한, fixture 본문 안내 |

동일 owner의 같은 requestId와 동일 입력은 같은 작업을 반환한다. 입력 또는 작업 종류가 다르면 409다. 생성 상태는 `QUEUED/RUNNING/READY/FAILED/RESULT_UNKNOWN`이며 stage는 진행 단계를 나타낸다. 완료 전 가짜 완성 아티팩트는 반환하지 않는다. READY 생성 작업은 `artifact`, READY 대사 작업은 `speechManifest`를 담는다. 완료 후 후속 대사가 추가돼도 원래 artifact는 바뀌지 않는다.

아티팩트의 `specHash`와 모든 clip.source.specSha256, characterId/profileId/bindingId를 연결한다. 소스의 아홉 필드는 [DesignedVoiceSource.schema.json](DesignedVoiceSource.schema.json)을 따른다. `audioSha256`는 앱이 실제 재생하는 정규화 WAV 전체 bytes이고, `rawAudioSha256`는 공급자에서 받은 변환 전 오디오다. 동일 캐릭터·동일 textSha256는 기존 clip과 파일을 재사용한다.

완성 PNG는 얼굴을 포함한다. RGBA8, 64..2048px, 최대 4,194,304 pixels, 8MiB이며 실제 투명/보이는 픽셀이 모두 있어야 한다. 앱은 PNG 전체에 호흡·기울기만 적용한다. WAV는 PCM16 mono 24kHz, 최대 30초·2MB다.

`OFFLINE_FIXTURE`는 기존 이미지·음원으로 연결을 시험한다. 입력에서 새 그림·음색·목적지 대사를 생성했다고 표시하면 안 된다. 기존 음원의 원래 source와 본문은 fixtureProvenance에 보존한다. 등록하지 않은 문장 합성은 `FIXTURE_TEXT_UNAVAILABLE`로 거절한다. `API` 모드는 필수 키와 계정에서 검증한 비용 설정이 없으면 외부 요청 0회로 실패한다. `DISABLED`는 신규 작업을 거절한다.

`cost.reservedMicros`는 호출 전 차감한 보수적 비용 상한이며 실청구액이 아니다. `actualMicros`는 확인되지 않으면 null이며 0으로 채우지 않는다. fixture만 실제 0이다. 가격 기준은 2026-11-03 USD, 구독료 별도다. 여정당 $0.30·초기 전체 $6을 초과하는 예약은 거절한다. 공급자 결과가 불명확하면 유료 요청을 자동 반복하지 않는다.

계정 영수증의 실제 비용은 오프라인 reconcile CLI로 확정한다. 실제 청구가 예약을 넘었을 때에도 금액을 숨기지 않고 overReservation/overBudget으로 표시하며 다음 한도 계산에 반영한다. Google 보관 음성의 만료 점검·월별 갱신 작업 준비와 같은 voiceId 유지 절차는 [서버 운영 안내](../../backend/README.md)를 따른다. 갱신 실행은 명시적인 API 설정과 일반 대사 비용 상한을 사용하며, 실제 공급자 갱신은 아직 검증하지 않았다.

스키마와 OpenAPI 재생성:

```sh
PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python backend/scripts/export_character_contracts.py
```
