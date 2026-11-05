# 두 번째 비교 후보 ASR

한국어 원어 preset Sohee의 새 WAV 4개와 ElevenLabs 공식 익명 공개 데모에서 받은 Anna MP3 1개를 같은 Whisper-small 모델로 각각 한 번 전사했다. 기존 12개 전사 결과는 보존했다. 추가 모델 다운로드와 원문 프롬프트는 사용하지 않았다.

| 실제 파일 | ASR 전사 | 정규화 문자오류율 |
|---|---|---:|
| `qwen-sohee/normal-arrival` | 와, 도착했다. 여기서 어떤 기억을 만나게 될까? | 0.00% |
| `qwen-sohee/normal-hello` | 안녕하세요 오늘의 여행도 함께할게요 | 0.00% |
| `qwen-sohee/small-smile-arrival` | 와... 도착했다... 여기서 어떤 기억을 만나게 될까? | 0.00% |
| `qwen-sohee/small-smile-hello` | 안녕하세요 오늘의 여행도 함께할게요 | 0.00% |
| `elevenlabs-public-demo/anna-common-arrival` | 안녕하세요 오늘의 여행도 함께 할게요 와 도착했다 여기서 어떤 기억을 만나게 될까? | 0.00% |

다섯 파일 모두 공백과 구두점을 제외한 원문과 일치했다. 이 ASR에서 삭제·치환·삽입 후보는 검출되지 않았다. 문장 부호와 띄어쓰기는 문자오류율에서 제외하므로 위 ASR의 쉼표·마침표·물음표가 원문과 달라도 CER는 0%다.

상용 MP3 원문은 PM이 공식 UI에 입력했다고 전달한 `안녕하세요. 오늘의 여행도 함께할게요. 와, 도착했다! 여기서 어떤 기억을 만나게 될까?`다. 정확한 상용 모델 ID·revision·합성 파라미터는 해당 익명 공개 데모에서 노출되지 않았다. 따라서 이 파일을 ElevenLabs의 특정 모델 버전으로 표기하지 않는다. 입력 출처와 이 한계는 `round2-input-manifest.json` 및 `round2-results.json`에 기록했다.

기존 libsoundfile 0.14로 MP3를 직접 읽었다. 추가 디코더 도구를 설치하지 않았다. 원본은 44.1kHz 모노 7.471초이며 ASR 입력 파형만 메모리에서 16kHz로 변환했다. Sohee WAV도 같은 전처리를 사용했다. 원본 음원 5개와 Sohee 메타데이터 4개, 기존 ASR 결과 13파일의 해시가 전후 일치한다.

자동 전사 일치만으로 정확한 발음·자연스러움·귀여움·문장 간 화자 동일성을 증명하지 않는다. 사람의 청취 평가가 필요하다. 이 CER 결과로 어느 모델이 더 자연스럽거나 좋은지 순위를 매기지 않는다.

상세 해시·전사·segment·설정은 `round2-results.json`, 보존 검증은 `round2-verification.json`, 실행 로그는 `round2-transcription.log`에 있다.
