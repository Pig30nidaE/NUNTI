# Dynamic journey voice transcription

Each of the thirteen WAVs was transcribed once with the existing local Whisper-small cache. No source text was supplied as a prompt.

| Source | Recognized Korean | Normalized CER |
| --- | --- | ---: |
| synthetic-coast-002/greeting | 바다 보러 가는 날이네? 오늘은 느긋하게 함께 가자 | 0.00% |
| synthetic-coast-002/arrival | 어떤 바다를 만나게 될까? 같이 천천히 바라보자 | 0.00% |
| synthetic-coast-002/common | 안녕 오늘은 나랑 같이 가자 | 0.00% |
| synthetic-mountain-001/common | 안녕 오늘은 나랑 같이 가자 | 0.00% |
| synthetic-mountain-001/greeting | 산을 만나러 가는 날이네 어떤 작은 발견이 기다릴까? | 0.00% |
| synthetic-mountain-001/arrival | 삼비칠 조금 담아둘까? 우리 천천히 둘러보자 | 16.67% |
| synthetic-coast-001/additional | 오늘의 기억은 내가 간직할게 | 0.00% |
| synthetic-coast-001/greeting | 바다 보러 가는 날이네 오늘은 느긋하게 함께 가자 | 0.00% |
| synthetic-coast-001/common | 안녕 오늘은 나랑 같이 가자 | 0.00% |
| synthetic-coast-001/arrival | 어떤 바다를 만나게 될까 같이 천천히 바라보자 | 0.00% |
| synthetic-city-001/arrival | 어떤 작품을 만나게 될까 마음에 드는 색을 찾아보자 | 0.00% |
| synthetic-city-001/greeting | 전시 보러 가는 날이네 어떤 색을 만나게 될까 | 0.00% |
| synthetic-city-001/common | 안녕 오늘은 나랑 같이 가자 | 0.00% |

CER removes whitespace and punctuation and compares NFC letters and numbers. ASR disagreements can be recognition errors. These results do not approve pronunciation, naturalness, cuteness, or distinct voice identity.

All input WAVs, metadata, old ASR artifacts, model cache files, and package inventory were preserved. Full results and edit alignments are in results.json.
