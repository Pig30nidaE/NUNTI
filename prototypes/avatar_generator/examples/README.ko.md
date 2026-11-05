# 내비 경로 스크린샷 시험자료

세 이미지 모두 코드로 만든 **합성 내비 화면**이다. 실제 지도·GPS·도로·실시간 내비에 연결하지 않았다. 장소 이름과 해안·구릉 배경도 가상의 시험 설정이다. 이 자료는 경로 입력과 추출을 시험하며 캐릭터 이미지를 제공하지 않는다. 세 예시가 아바타 카탈로그나 생성 가능한 여정의 수를 제한하지 않는다.

`synthetic-city.png`, `synthetic-coast.png`, `synthetic-hills.png` 각각에 같은 이름의 JSON이 있다. JSON의 `groundTruth.pixelPoints`는 이미지에 파란 선을 그릴 때 쓴 전체 화면 픽셀 좌표다. `route.points`는 이를 전체 이미지 0–1 좌표로 변환한 값이다. 이미지 원본 SHA-256, 합성 출처, 가상 목적지·특성·목적을 함께 기록했다. `index.json`은 이 세 자료를 묶은 목록이다.

이미지에 적힌 A와 B는 사람이 대조할 출발·목적지 표시다. 추출기는 문자를 읽거나 목적지 방향을 추측하지 않는다. 추출 순서는 결정적이지만 실제 진행 방향과 같다는 보장이 없으므로 사용자가 원본 위 선과 시작·끝을 확인해야 한다. 화면 좌표를 위경도·거리·시간·지형 근거로 사용하지 않는다.

## 재현

프로젝트 루트에서 Pillow가 설치된 Python으로 실행한다. 자료 생성과 추출 검증에 네트워크나 API 키는 필요 없다.

```sh
python prototypes/avatar_generator/examples/build_examples.py
python prototypes/avatar_generator/examples/verify_examples.py
PYTHONPATH=backend python -m pytest backend/tests/test_avatar_navigation.py -q
```

`verify_examples.py`는 실제 `extract_route()`를 실행하고 `.overlay.png` 세 장과 `extraction-checks.json`을 만든다. 분홍 선은 추출 결과이며 원본 PNG는 변경하지 않는다. 이 미리보기는 UI에서 사용자의 원본 대조와 확인을 생략하는 근거가 아니다.

추출 함수는 PNG/JPEG 최대 8MiB, 변당 64–4096px, 전체 8,388,608 픽셀을 받는다. 최대 512px 표본에서 유채색 성분을 나누고, 연결된 선을 세선화한 뒤 순서 있는 2–512점 polyline을 반환한다. 선택적 색 힌트는 `blue`, `cyan`, `purple`, `green`, `red`, `orange`, `#RRGGBB`, RGB 정수 세 값이다.

복수 경로·의미 있는 분기·폐곡선·색 도로 격자·큰 배경 면은 자동 확정하지 않는다. 불명확하면 `ValueError` 코드로 거절하고 색 힌트나 다른 스크린샷이 필요하다. 회색 경로, 점선, 화면 위 장식에 가려지거나 끊긴 경로, 매우 얇은 선은 지원을 보장하지 않는다. confidence는 검증된 성공 확률이 아닌 색·형상에 따른 보수적인 휴리스틱 값이다. 모든 성공 결과에도 사용자 확인과 화면 좌표·진행 방향 경고를 붙인다.

## JSON 직접 입력 예시

`route-file.example.json`은 사용자가 수정하거나 파일 입력 UI에서 읽을 수 있는 형식이다. 목적지·특성·목적과 `route.points`를 함께 둔다. `confirmed:false` 상태를 보존하고, UI에서 경로를 확인한 뒤에만 생성 요청을 보낸다. 생성 요청의 `requestId`는 호스트가 새 여정 UUID로 추가한다.

```json
{
  "destination": {"name": "목적지", "traits": "사용자가 제공한 장소 특성"},
  "purpose": "이번 이동의 목적",
  "route": {
    "points": [[0.10, 0.80], [0.35, 0.55], [0.65, 0.55], [0.90, 0.15]],
    "inputOrigin": "ROUTE_FILE",
    "sourceLabel": "원본 경로 자료의 출처",
    "confirmed": false
  }
}
```

실제 내비 자료를 넣을 때는 동일한 경로의 원본 스크린샷·좌표 JSON, 공급자·조회 시각·좌표계·원본 해시와 재사용 조건을 보관한다. 이 합성 자료에는 OSM이나 상용 지도 데이터가 없어 해당 공급자의 데이터를 사용했다고 표시하지 않는다.

## 실행 확인

실제 raster 입력과 paired 중심선의 양방향 오차를 비교한다. PNG/JPEG, 색 힌트 6종, 복수 대안, 격자·분기·폐곡선·배경, EXIF 회전, 잘못된 파일·크기를 회귀 검사한다. 이 결과를 실제 한국 내비 경로 정확도나 임의 사진의 추출 성공으로 확대하지 않는다.
