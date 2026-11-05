# 여정 캐릭터 생성 레시피 프로토타입

Python 3.9 이상과 표준 라이브러리만 사용하는 독립 CLI다. 목적지의 의미 태그, 경로 정보, 방문 목적, 기존 컬렉션 기록으로 생성 레시피를 정한다. Android, SERVER, wire v1, 외부 생성 모델과 연결하지 않는다. 외부 키나 다운로드가 필요 없다.

현재 결과는 `RECIPE_ONLY`다. 이미지, rig, 애니메이션, 음성 파일을 생성하지 않는다. 귀여움과 소장 욕구, 운전습관 개선 효과도 검증하지 않았다. 비교할 시안을 만들 때 쓸 입력과 여정별 정체성 보존 규칙을 실험한다.

사용자가 선택한 C 방향인 반투명 기념 오브젝트를 새 레시피의 아트 방향으로 적용했다. 캐릭터 안에 여정을 떠올리게 하는 작은 무늬와 부드러운 빛을 제안한다. 기존 ledger에 이미 저장한 캐릭터는 최초 레시피를 보존한다.

## 실행

저장소 루트에서 실행한다. 아래 ledger는 본인이 선택한 독립 로컬 파일이다. 같은 파일에 CLI를 동시에 실행하지 않는다.

```sh
python3 prototypes/journey_characters/recipe_cli.py generate \
  --input prototypes/journey_characters/examples/coastal_rest.json \
  --ledger /tmp/nunti-keepsake-journey-ledger.json

python3 prototypes/journey_characters/recipe_cli.py generate \
  --input prototypes/journey_characters/examples/coastal_rest_next.json \
  --ledger /tmp/nunti-keepsake-journey-ledger.json
```

같은 입력을 다시 실행하면 기존 결과를 그대로 반환한다. 두 번째 예제는 같은 경로의 다른 여정이다. `characterId`와 `seed`를 바꾸고, 첫 여정과 다른 몸체 계열을 선택한다. 새 색이나 장식만 붙여 새 캐릭터로 판정하지 않는다.

대표 합성 여정 4개를 새 임시 ledger에서 순서대로 실행해 재현한다.

```sh
python3 prototypes/journey_characters/render_samples.py \
  --output /tmp/nunti-journey-sample.json
python3 prototypes/journey_characters/verify.py
```

이 폴더의 `sample-output.json`은 같은 실행 경로로 보존한 출력이다. 해안도시 휴식, 산악 캠핑, 도심 전시 관람, 같은 해안경로의 다음 여정 순이다. 실제 위치나 이동 기록을 사용하지 않았다.

## 레시피를 이미지 프롬프트로 변환

```sh
python3 prototypes/journey_characters/build_illustration_prompt.py \
  --input prototypes/journey_characters/sample-output.json \
  --recipe-index 0 \
  --output /tmp/nunti-illustration-prompt.txt
```

`--input`은 단일 레시피 JSON이나 `sample-output.json`을 받는다. sample의 기본 `--recipe-index`는 0이다. `sample-illustration-prompt.txt`는 첫 합성 여정으로 만든 실제 출력이다. 시각 필드만 명시적으로 골라 몸체·실루엣·비율·재질·색·내부 무늬·빛과 얼굴·카메라 문법을 영문 C 방향 프롬프트에 담는다. 고정 3/4 시점, 전신, 살아 있는 캐릭터 한 명, 반투명 수지와 불투명 크림색 얼굴, 실제 alpha 투명 배경을 요구한다. UI와 문자 등은 제외한다.

파일 첫 부분의 캐릭터 ID와 레시피 SHA-256은 추적용 입력 메타데이터이며 그림에 표시할 내용이 아니다. personality·voice·seed·정밀 주소·좌표·도로 사실은 프롬프트로 옮기지 않는다. 해시는 전체 입력 레시피의 정규화 JSON을 계산한 값이며, 원문 필드를 노출하지 않는다.

출력 텍스트는 사용자가 내장 imagegen에 전달할 수 있다. 이 CLI가 앱이나 이미지 API를 자동 호출하지는 않는다. 투명 배경 문구는 생성 요청이며 실제 결과의 alpha 검증을 대신하지 않는다. 같은 입력의 프롬프트는 다시 만들 수 있지만, seed나 프롬프트만으로 같은 이미지가 재현된다고 보장하지 않는다. 이전 세계관 레시피는 그대로 보존하되 이 변환기는 선택된 C 세계관만 지원한다.

## 입력과 설계축

`requestId`는 요청 재전송 식별자, `journeyId`는 한 번의 이동을 식별한다. 둘 다 위치나 이름 대신 불투명한 ID를 사용한다. 기존 이동을 reroute할 때는 `journeyId`를 유지한다. 새 이동이면 새 `journeyId`를 사용한다. 정밀 주소와 GPS 필드는 지원하지 않으며 입력 경계에서 거절한다.

| 입력 | 레시피에 반영되는 축 |
| --- | --- |
| `destination.semanticTags` | 반투명 재질, 팔레트, 내부 모티브, 이름 어근 |
| `route.semanticTags` | 몸체 계열의 창작 모티브 선호, 내부 무늬의 배치 |
| `route.distanceKm` | 몸체 폭과 높이의 비율 |
| `purpose` | 성격, 내부 빛, 이름의 어감, 희망 음성 표현 |
| ledger의 기존 캐릭터 | 몸체 계열과 형태 반복 억제 |

새 레시피의 세계관은 `translucent_keepsake_25d`, registry 버전은 `translucent-keepsake-0.2`다. 둥근 반투명 수지 몸체, 얕은 깊이에 담긴 작은 내부 모티브, 흐린 내부 빛, 작은 얼굴, 부드러운 접지 그림자와 3/4 시점이라는 시안용 문법을 유지한다. 몸체는 조약돌, 물방울, 콩, 새싹, 쿠션, 랜턴, 구름, 도토리 계열의 16개 형태 중에서 고른다. 이 이름은 시각 레시피의 분류이며 완성된 3D 자산이 아니다.

`design.interiorIntent`에는 목적지 모티브, 경로 태그에 따른 배치, 방문 목적에 따른 빛의 색·위치·확산을 적는다. 예를 들어 해안도시는 물빛 반투명 재질과 작은 진주빛 거품, 해안 경로는 얕은 물결 리본, 휴식 목적은 아래쪽의 옅은 따뜻한 빛으로 이어진다. 산악 캠핑은 안개빛 내부 모티브와 등고선 곡선, 작은 호박색 빛을 쓴다. 도심 전시는 유백색 반투명 재질과 색 조각, 작은 둥근 격자, 연보라 빛을 제안한다. 이는 렌더링 결과가 아닌 정적 시안 지시이며 `motionIntent=STATIC_ONLY`, `renderingStatus=NOT_RENDERED`다.

반복 억제는 기존 몸체 계열 사용 횟수, 형태 사용 횟수, 경로 태그와의 모티브 일치, seed 기반 동률 해소 순서로 비교한다. 8개 몸체 계열을 한 번씩 사용한 뒤부터 계열 반복이 생긴다. 무한히 새로운 실루엣을 만드는 알고리즘은 아니다. 긴 거리나 특정 경로는 희귀도, 더 좋은 보상, 점수와 연결하지 않는다.

`purpose`가 없거나 null이면 `UNSPECIFIED`로 남긴다. 중립적인 성격·빛·음성 제안은 기본 창작 선택이다. 사용자가 휴식, 캠핑 등의 목적을 밝혔다고 기록하지 않는다. 지원 태그와 목적은 `registry.json`에서 확인한다. 복수 목적지 태그는 registry 순서의 첫 일치 항목을 쓴다. 예를 들어 `city`와 `art`가 함께 있으면 `art`가 재질과 팔레트를 정한다. 내부 무늬 배치도 `routeInteriorStyles`의 첫 일치 항목을 쓴다. 목적지·경로 태그와 목적 모두 유한한 registry에서 고른다.

## 정체성, 재시도, 중단 복원

`seed`는 여정 ID에서 계산한 16자리 16진 문자열이다. 큰 정수를 다른 실행 환경에서 읽을 때 생기는 정밀도 손실을 피한다. `characterId`도 여정 ID에서 결정한다. 새 캐릭터의 형태 선택에는 기존 ledger 이력을 사용한다. 서로 다른 ledger는 서로 다른 컬렉션으로 취급한다.

한 번 저장된 레시피 전체는 최초 결과를 유지한다. 같은 요청의 중복, 같은 여정의 새 요청, 변경된 입력, reroute 모두 기존 결과를 반환한다. 동일 `requestId`를 다른 `journeyId`에 재사용하면 오류로 거절한다. 입력 변경을 보낸 사실을 별도 revision으로 수집하는 기능은 없다. 기록된 `firstRequestDigest`는 각 요청 ID로 처음 받은 정규화 입력의 해시다.

이전 `soft_sculpt_25d` 레시피가 저장된 ledger도 그 캐릭터를 자동으로 재질 변경하거나 내부 무늬를 추가하지 않는다. 새 아트 방향을 시험하려면 새 여정을 만들거나 별도의 빈 ledger를 선택한다. ID·seed와 voice 정체성 계산식은 아트 방향 변경 전후에 유지했다. 기존 캐릭터를 바꾸는 마이그레이션은 이번 범위에 포함하지 않는다.

ledger는 `journeys`에 최초 레시피를, `requests`에 요청과 여정의 연결을 저장한다. 임시 파일 쓰기와 fsync 후 원자적 replace, 디렉터리 fsync를 수행한 다음 결과를 출력한다. 저장 직전 중단이면 이전 ledger가 남고, 저장 직후 중단이면 재실행이 저장된 결과를 돌려준다. 쓰기 도중 남은 임시 파일은 다음 저장 때 제거한다. 손상된 JSON이나 지원하지 않는 ledger 버전은 덮어쓰지 않는다.

지원 범위는 단일 CLI writer와 로컬 파일시스템이다. 동시 writer 조정, 분산 트랜잭션, 파일 손상 자동 복구, 레지스트리 마이그레이션, 서비스 배포를 제공하지 않는다. ledger를 삭제하면 컬렉션 이력을 잃는다. 같은 여정의 ID와 seed는 다시 계산할 수 있어도, 중간 컬렉션 이력을 복원할 수 없으므로 전체 레시피 복구를 보장하지 않는다.

## 창작 입력, 도로 사실, 음성

창작 의미 태그와 `verifiedRoadFacts`는 별도 필드다. `mountain`, `curving`, `highway` 태그가 있어도 도로 사실을 자동으로 검증하지 않는다. 네 합성 예제는 모두 `UNKNOWN`이다. 명시적으로 공급받은 `VERIFIED`의 도로 종류와 근거 출처는 복사만 한다. 이 프로토타입은 그 출처를 조회하거나 진위를 검증하지 않는다.

레시피에 저장한 도로 사실의 범위는 `CREATION_SNAPSHOT_NOT_CURRENT_DRIVING_STATE`다. reroute 뒤에도 이 생성 시점 기록은 유지한다. 실제 운전 판단에 쓰는 현재 도로 상태와 안전 정책은 별도의 검증 경로에서 유지해야 한다. 이 파일은 그 경로와 연결하지 않는다.

`voiceIntent`는 성격에 맞는 음색, 속도, 정서 표현을 희망 메타데이터로 적는다. `identityKey`는 캐릭터별로 보존한다. image, animation, TTS provider는 모두 `UNCONNECTED`, 음성 상태는 `UNBOUND_INTENT`, 확인된 지원 제어는 빈 목록이다. 공급자 지원과 실제 음질, 캐릭터별 목소리 차이는 미검증이다.

오프라인 대체 제안은 `same_character_asset_else_pending_or_silent`다. 같은 캐릭터의 화자 바인딩과 같은 문장에 맞는 자산만 재사용하고, 없으면 준비 대기 또는 무음을 사용한다는 방향이다. 기기 기본 화자로 자동 변경하는 전략을 제안하지 않는다. 실제 오디오 자산이 없으므로 `assetAvailability=UNVERIFIED`, 실행 상태는 `implementationStatus=PROPOSAL_ONLY`다. 자산 검색·재생·대기·무음 처리와 캐릭터 음성 정체성을 구현하거나 보장한 결과가 아니다. 기존 ledger의 최초 레시피는 그대로 보존되므로, 실제 runtime에 연결할 때의 대체 정책은 별도로 확정해야 한다.

## 검증 근거와 남은 일

`verify.py`는 실제 CLI를 매번 새 프로세스로 실행하고 출력과 ledger를 읽는다. 기존 15개 검증은 요청 중복과 reroute의 출력 동일성, 이전 아트 방향의 저장 결과 보존, 같은 경로의 새 몸체 계열, 8개 계열 소진 전 반복 억제, 재질·내부 모티브·경로 무늬·빛을 포함한 입력축별 영향, 목적 누락, 도로 사실 분리, 최초 저장 및 기존 ledger 저장의 replace 전후 강제종료와 복원, 요청 ID 충돌 거절, 손상 JSON 보존, GPS 입력 거절을 확인한다. 대표 합성 여정의 ID·seed·voice 정체성이 이전 프로토타입과 같다는 것도 비교한다. 프롬프트 변환 검증 2개는 선택한 시각 재료·형태가 반영되고, 위치·도로 사실·성격·음성·seed 원문이 노출되지 않음을 확인한다. 총 17개 실행 결과를 `verification-result.txt`에 보존했다.

다음 단계에는 이 레시피의 시안 생성과 실루엣 평가, 사람이 보는 귀여움·소장 욕구 비교, rig와 표정·동작 설계, 실제 TTS 제어와 청취 평가가 필요하다. 이후에 Android와 서버의 ID·비동기 생성·컬렉션 계약을 합의해야 한다. 기존 기능이나 공통 wire는 이번 프로토타입에서 수정하지 않았다.
