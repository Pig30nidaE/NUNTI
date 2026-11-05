# Chatterbox Multilingual V3 한국어 비교

Qwen3-TTS 이외의 실제 모델을 같은 두 문장으로 비교한다. 공식 Chatterbox 코드를 사용하고 `t3_model="v3"`를 명시한다. 기본 조건 음성과 Qwen VoiceDesign의 합성 레퍼런스 조건을 분리한다. 실제 사람의 녹음은 사용하지 않는다. 자연스러움·귀여움·모델 우열은 청취 전 미검증이다.

`listen.html`을 열면 실제 세 조건을 문장별로 비교할 수 있다. WAV 네 개의 형식·해시·비어 있지 않은 PCM·클리핑 0을 검증했다. Mac MPS 로드는 14.69초였다. 실제 합성 시간은 기본 음성 24.72초·5.11초, 합성 레퍼런스 조건 17.21초·7.40초다. 첫 호출 준비 비용과 레퍼런스 전처리 비용이 포함되어 순수 모델 성능 지표로 해석하지 않는다.

## 설치와 재현

저장소 루트에서 실행한다. Python 3.12와 기존 `.local/journey-voice/uv/bin/uv` 실행 파일이 필요하다. 설치·가중치·HF·중국어 tokenizer 캐시는 `.local/chatterbox-audition/`에 둔다. 기존 TTS 환경은 수정하지 않는다.

```sh
sh prototypes/chatterbox_audition/setup.sh
python3.12 prototypes/chatterbox_audition/bootstrap.py models
.local/chatterbox-audition/venv/bin/python prototypes/chatterbox_audition/generate.py --device mps --conditions both
python3 prototypes/chatterbox_audition/verify.py
```

Mac GPU 접근이 제한된 실행 환경에서는 MPS를 사용할 수 있는 실행 권한이 필요하다. 생성기는 MPS를 요청했을 때 CPU로 조용히 전환하지 않는다. Qwen 등 다른 모델의 추론 프로세스를 종료하고 단독으로 실행한다. 기존 WAV와 메타데이터가 있으면 덮어쓰지 않는다.

## 비교 조건

| 조건 | 음성 근거 | 대사 |
| --- | --- | --- |
| `builtin-hello` | 모델에 포함된 기본 `conds.pt` | 안녕하세요. 오늘의 여행도 함께할게요. |
| `builtin-comfort` | 같은 기본 조건 | 천천히 가도 괜찮아. 나는 네 옆에 있을게. |
| `qwen-reference-hello` | Qwen 합성 `round-smile-hello.wav` | 안녕하세요. 오늘의 여행도 함께할게요. |
| `qwen-reference-comfort` | 같은 Qwen 합성 레퍼런스 | 천천히 가도 괜찮아. 나는 네 옆에 있을게. |

Qwen 레퍼런스의 원래 모델은 `mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit`다. revision·원문·스타일 지시·오디오 해시는 각 `samples/qwen-reference-*.json`에 기록한다. 이것은 Qwen과 Chatterbox의 결합 조건이다. Chatterbox가 자연어만으로 새 음색을 설계한 결과로 해석하면 안 된다.

추론 매개변수는 seed 20261102, 한국어 `ko`, exaggeration 0.4, CFG 0.5, temperature 0.8이다. 나머지는 공식 기본값을 사용한다. 음정·속도·노이즈 제거·음량 보정 후처리는 없다. 공식 코드가 반환하기 전에 적용하는 PerTh 워터마크는 유지하고, 반환 파형을 PCM16 WAV로 인코딩한다.

## 증거와 범위

- `model-lock.json`은 공식 코드·모델·PerTh 커밋과 선택 파일의 원본 해시를 고정한다.
- `download-verification.json`은 선택한 여섯 파일 3,208,951,924 bytes의 실제 해시를 기록한다. 전체 모델 저장소의 다른 세대 가중치는 받지 않는다.
- `requirements.lock.txt`는 실제 설치한 패키지 버전이다.
- `generation.log`, `runtime-summary.json`, `samples/*.json`은 실제 실행 장치·추론 시간·파형 수치·원문을 기록한다.
- `verification.json`은 파일 해시·PCM 형식·원문 메타데이터·합성 레퍼런스 출처를 검증한다. 발음이 원문과 일치한다는 청취 또는 ASR 검증을 대신하지 않는다.

첫 실행에서 upstream tokenizer가 한국어에 사용하지 않는 중국어 pkuseg 모델을 사용자 홈 아래 새 캐시로 자동 다운로드했다. 새로 만들어진 경로와 파일만 확인해 실험 캐시로 이동했다. `cache-relocation.json`에 근거를 남겼고, 생성기에 `PKUSEG_HOME`을 지정해 재현 시 같은 위치를 사용한다. Cangjie의 upstream `main` 조회는 전용 오프라인 HF 캐시에서 고정 모델 SHA로 연결한다. 최초 로그의 Cangjie 경고는 한국어 분절 기능을 누락했다는 뜻이 아니다.

## 출처와 라이선스

공식 [Chatterbox 저장소](https://github.com/resemble-ai/chatterbox)와 [모델 카드](https://huggingface.co/ResembleAI/chatterbox)를 사용한다. 코드·모델의 라이선스는 MIT다. `licenses/chatterbox-MIT.txt`에 고정 코드의 원문을 보존한다. PerTh 커밋은 공식 저장소의 `ff1c8ac55a976971245cdd53c18d6131ca00d993`다. PerTh MIT 원문은 `licenses/PerTh-LICENSE.txt`에 보존한다. [공식 PerTh 저장소](https://github.com/resemble-ai/Perth)
