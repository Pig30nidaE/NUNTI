# 한국어 원어 프리셋 Sohee 비교

이 실험은 Qwen CustomVoice 1.7B의 한국어 원어 프리셋 `Sohee`를 기준으로 읽는다. 앞선 VoiceDesign의 영어 설명으로 만든 음색과 Base 참조 복제는 사용하지 않는다. 참조 음성도 없다. 기존 후보에 대한 A > B의 상대적 선호를 제품 품질 승인으로 해석하지 않으며, 이전 Base 결과의 최종 채택을 철회한 상태에서 새 기준을 비교한다.

`listen.html`에서 같은 두 문장의 기본 음성과 약한 미소 연기 조건을 들을 수 있다. 기본 조건의 `instruct`는 빈 문자열이다. 약한 조건의 지시는 `Native Korean conversational speech with a small smile.`이다. 이 지시는 프리셋의 연기를 조절하며, 새 음색을 설계하는 VoiceDesign 호출이 아니다.

## 실제 생성 결과

| 조건 | 대사 | 길이 | 실제 합성 시간 |
| --- | --- | --- | --- |
| 기본 Sohee | 안녕하세요. 오늘의 여행도 함께할게요. | 2.88초 | 1.96초 |
| 기본 Sohee | 와, 도착했다! 여기서 어떤 기억을 만나게 될까? | 5.84초 | 3.61초 |
| 가벼운 미소 | 안녕하세요. 오늘의 여행도 함께할게요. | 3.44초 | 2.17초 |
| 가벼운 미소 | 와, 도착했다! 여기서 어떤 기억을 만나게 될까? | 4.80초 | 2.91초 |

실제 모델을 로드한 뒤 `custom_voice` 모델 종류와 프리셋 목록의 `sohee`, 화자 ID `2864`를 확인했다. 모델 설정의 한국어 ID는 `2064`다. `generate_custom_voice(speaker="Sohee", language="Korean")`로 네 파일만 합성했다. 모델 로딩은 1.43초, 실행에서 관측한 MLX peak 메모리는 5,770,274,049 bytes였다. 프로세스는 exit 0으로 종료했다.

오디오는 원음 24kHz·모노·PCM16 WAV다. 음정·속도·음량·노이즈 보정 후처리를 적용하지 않았다. 네 파일 모두 full-scale 샘플 0개를 확인했다. 파일 형식·출처·원문 메타데이터의 검증은 자연스러움·발음·귀여움의 청취 승인을 뜻하지 않는다.

## 재현과 보존

저장소 루트에서 실행한다. 기존 MLX 가상환경은 그대로 사용하며 패키지를 설치하거나 바꾸지 않는다.

```sh
python3.12 prototypes/qwen_sohee_audition/download_model.py
.local/journey-voice-v3/venv/bin/python prototypes/qwen_sohee_audition/generate.py
.local/journey-voice-v3/venv/bin/python prototypes/qwen_sohee_audition/verify.py
```

완성된 파일이 있는 현재 상태에서는 생성 명령이 캐시만 읽는다. 메타데이터의 원문·화자·모델·설정·런타임·후처리를 현재 고정 자료와 대조하고, 실제 WAV 해시·헤더·길이를 확인한다. 불일치나 부분 결과를 자동 덮어쓰지 않는다.

실제 별도 프로세스 재시작에서 네 cache hit와 `modelLoaded=false`를 확인했다. 설정·모델 lock·네 WAV·네 메타데이터 등 10개 파일의 재실행 전후 해시가 동일했다. 기존 Qwen 가상환경의 패키지 목록과 원래 requirements lock도 그대로였다. 결과는 `verification.json`에 있다.

모델과 HF 캐시는 `.local/qwen-sohee-audition/`에 분리했다. 새 다운로드는 2,397,848,446 bytes다. 공식 해시가 같은 speech tokenizer 682,293,092 bytes는 기존 파일을 읽기 전용 심볼릭 링크로 재사용했다. 이전 WAV·바인딩·Android 코드는 수정하지 않았다.

## 출처와 라이선스

[Qwen 공식 화자 목록](https://github.com/QwenLM/Qwen3-TTS#custom-voice-generate)은 Sohee를 한국어 원어 여성 화자로 설명하고, 최적 품질에는 화자의 원어 사용을 권장한다. 실험 모델은 [MLX Community CustomVoice 1.7B 8bit 고정 revision](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit/tree/41d3337e8b7f2843a75841595fc14e4b9a7a4b96)이다. Qwen 제작자의 원래 런타임 대신 기존 MLX-Audio 0.6.3·MLX 0.32.4로 실행했다.

`model-lock.json`, `model-card.md`, `source-refs.json`, `generation.log`, `runtime-summary.json` 및 각 `samples/*.json`에 실제 출처·revision·원문·해시·설정·실행 수치를 보존했다. 모델·Qwen 코드는 Apache-2.0, MLX-Audio는 MIT다. 라이선스 원문은 `licenses/`에 있다.
