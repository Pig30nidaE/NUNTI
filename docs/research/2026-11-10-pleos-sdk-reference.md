# PLEOS Connect SDK 문서 로컬 참고 자료

2026-11-10 수집. PLEOS Connect SDK 한국어 사이트맵의 문서 1,911개를 보관했다. 수집 당시 Vehicle SDK 공식 Maven의 최신 공개 버전은 2.3.2다. 문서와 실제 앱의 SDK·차량 서비스 버전이 일치하는지 별도로 확인해야 한다.

- [수집 범위와 주의사항](../../.local/pleos-sdk-2026-11-10/읽어주세요.md)
- [전체 목차와 공식 문서 링크](../../.local/pleos-sdk-2026-11-10/전체-목차.md)
- [API 본문 전체 검색 파일](../../.local/pleos-sdk-2026-11-10/전체-API-본문-검색.txt)
- [일반 가이드 모음](../../.local/pleos-sdk-2026-11-10/본문-있는-가이드-모음.txt)
- `.local/pleos-sdk-2026-11-10/pages/`: 페이지별 텍스트와 원본 HTML

프로젝트 루트에서 검색 예시:

```sh
rg -in 'rain|wiper|night' .local/pleos-sdk-2026-11-10/전체-API-본문-검색.txt
rg -in 'onTripFuelEconomyUpdated' .local/pleos-sdk-2026-11-10/pages --glob '*.dokka.txt'
```

API 상세는 브라우저의 Shadow DOM에 표시되는 Dokka 원문을 JavaScript 번들에서 추출했다. API를 확인할 때는 `.dokka.txt` 또는 `.dokka.html`을 사용한다. 초기 정적 HTML 추출본 `.txt`와 `manifest.json`의 `heading_only`는 API 상세의 유무를 판단하는 기준이 아니다. `dokka-manifest.json`에서 상세 추출 결과를 확인한다. 텍스트에는 복사 버튼 등 UI 문구가 섞일 수 있으므로 정확한 내용은 원문 링크나 `.dokka.html`도 확인한다.

`.local/`은 Git에서 제외되므로 문서 본문은 이 컴퓨터의 로컬 참고 자료이며 저장소를 복제한 다른 환경에는 자동으로 포함되지 않는다.
