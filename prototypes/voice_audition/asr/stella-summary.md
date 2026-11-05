# Stella 공개 데모 추가 ASR

공식 UI에서 `Stella - Steady, Clear and Cheerful`을 선택해 받은 MP3 한 개를 기존 Whisper-small 모델과 동일한 greedy 설정으로 한 번 전사했다. 다른 결과는 다시 전사하지 않았고, 원문은 ASR 프롬프트에 주지 않았다.

ASR 전사:

> 안녕하세요 오늘의 여행도 함께 할게요 와 도착했다 여기서 어떤 기억을 만나게 될까

정규화 CER는 0%이며 삭제·치환·삽입 후보는 없다. 마지막 `여기서 어떤 기억을 만나게 될까`도 전사에 포함됐다. 다만 ASR은 틀리거나 들리지 않은 말을 추정할 수 있으므로 실제 끝 잘림이 없다는 사람의 청취 검증을 대체하지 않는다. 구두점과 띄어쓰기는 CER에서 제외한다.

원본 MP3와 메타데이터의 해시, 기존 ASR 산출물 23파일의 해시가 전후 일치한다. MP3 SHA-256은 `77052532dd52b1a6539d660dc1a516ec998d6a06144a8c0d0e2611777718dc4b`다. 상세 전사·편집 정렬·출처는 `stella-results.json`, 재검증은 `stella-verification.json`, 실행 로그는 `stella-transcription.log`에 기록했다.

공개 익명 데모의 정확한 모델 ID·revision·합성 파라미터는 미노출이다. 특정 ElevenLabs 모델 버전으로 표기하지 않는다. 이 검사는 자연스러움·귀여움·화자 동일성을 판정하지 않는다.
