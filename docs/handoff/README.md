# Nunti 세션 인수인계

작성 기준은 2026-11-02, Asia/Seoul이다. PM이 기존 TTS·AVATAR·SERVER 세션에 현황 보고를 요청하고, 통합 저장소 및 보존된 검증 증거와 대조했다.

저장소: [Pig30nidaE/NUNTI](https://github.com/Pig30nidaE/NUNTI)

구현 기준 커밋은 `bc0a9483d4baaefee397635dd3dc01fe2b7f4b3e`다. 이 문서가 추가된 커밋은 그 이후이며, 새 로컬은 원격 `main`의 인수인계 문서를 포함한 최신 커밋에서 시작한다.

| 읽을 문서 | 용도 |
| --- | --- |
| [전체 구현·작업 상태](STATUS.md) | 완료 범위, 미구현 연결, 검증 수준, 역할과 다음 우선순위 |
| [새 로컬 복원 절차](RELOCATION.md) | clone, 환경 설치, 검사, 독립 worktree 구성 |
| [이관 검증 결과](verification.json) | 문서·보존 증거 검사 결과. 신규 기능 테스트와 구분 |
| [PM 프롬프트](prompts/pm.md) | PM 세션에 그대로 붙여넣을 시작 지시 |
| [TTS 프롬프트](prompts/tts.md) | TTS 세션에 그대로 붙여넣을 시작 지시 |
| [AVATAR 프롬프트](prompts/avatar.md) | 아바타 세션에 그대로 붙여넣을 시작 지시 |
| [SERVER 프롬프트](prompts/server.md) | 서버 세션에 그대로 붙여넣을 시작 지시 |
| [TTS 담당 보고](reports/tts.md) | 기존 담당 세션의 직접 보고 |
| [AVATAR 담당 보고](reports/avatar.md) | 기존 담당 세션의 직접 보고 |
| [SERVER 담당 보고](reports/server.md) | 기존 담당 세션의 직접 보고 |

현재 상태는 합성 입력 기반의 통합 MVP다. 공식 Pleos 에뮬레이터에서 주차 상태의 아바타 표시와 실제 ON_DEVICE TTS 출력까지 확인했다. 실제 주행 상태 전환, 실제 경로·운전 이벤트 수신, Android 서버 동기화, 최종 점수·코멘트 생성은 완료되지 않았다.

이관 파일·과거 증거의 무결성 검사는 루트에서 실행한다.

```sh
python3 scripts/verify_handoff.py
```

이 검사는 과거 로그·오디오 및 문서 보존 여부를 검사한다. 새 로컬에서 앱이나 서버를 실행한 결과는 [복원 절차](RELOCATION.md)에 따라 별도로 확인한다.
