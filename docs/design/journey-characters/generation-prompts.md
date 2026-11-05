# C 방향 캐릭터 제작 프롬프트

이 문서는 모델 역할별 입력·출력 초안이다. 실제 앱에 연결된 프롬프트 체인이 아니다. 현재 이미지 시안에 사용한 전체 프롬프트는 [image-prompts.json](image-prompts.json)에 보존했다. 고정 세계관은 사용자가 선택한 C · 반투명 기념 오브젝트다.

레시피에서 시각 지시를 만드는 실제 도구는 [프롬프트 변환기](../../../prototypes/journey_characters/build_illustration_prompt.py)다. [해안 여정의 출력 문장](../../../prototypes/journey_characters/sample-illustration-prompt.txt)을 내장 image_gen에 전달해 [단독 시안](concepts/recipe-coastal-001.png)을 생성했다. 이 한 장은 실제 alpha 범위 0~255를 확인했다. 앱 자동 호출·레이어 제작·귀여움 품질 평가까지 완료한 결과는 아니다.

## 입력을 준비하는 프롬프트

```text
역할: 여정 모티브 편집자.
입력: 사용자가 선택한 넓은 목적지 유형, 방문 목적 또는 UNSPECIFIED,
      창작 경로 태그, 별도로 검증된 route snapshot, 소장 descriptor 목록.
출력: creativeContext와 verifiedFacts를 별도 JSON 객체로 반환한다.
      각 모티브에 USER_DECLARED, SYNTHETIC, VERIFIED_SNAPSHOT 중 실제 출처를 붙인다.
규칙: 정밀 주소, GPS, 원문 목적지, 실제 이동 궤적을 출력하지 않는다.
      사용자 목적을 추측해 채우지 않는다. 창작 태그로 도로·위험·점수를 만들지 않는다.
      verifiedFacts는 입력에서 허용된 사실만 복사하며 UNKNOWN을 유지한다.
```

제품의 입력 검증·비식별화는 프롬프트 문장만으로 보장하지 않는다. 허용 필드와 taxonomy를 코드 경계에서 제한한다. 현재 CLI는 지정 외 입력과 정밀 위치 필드를 거절한다.

## 캐릭터를 설계하는 프롬프트

```text
역할: Nunti 캐릭터 아트디렉터.
세계관: 살아 있는 반투명 기념 동반자. 서리 낀 수지, 부드러운 입체감,
        불투명 크림 얼굴, 절제된 내부 무늬·빛, 따뜻한 고정 조명.
입력: creativeContext, collectionDescriptors, 허용 rig catalog, 고정 생성 seed.
과제: 이번 여정에서 태어난 세 후보를 JSON으로 제안한다.
출력 필드: candidateId, bodyTopology, silhouette, bodyProportions, faceProportions,
           materialIntent, palette, interiorMotif, lightIntent, personality,
           nameSuggestion, voiceIntent, creativeSources, noveltyComparedWith.
규칙: 몸 구조 또는 비례가 최근 가까운 캐릭터와 구별돼야 한다.
      새 이름·색·의상만으로 차별성을 충족하지 않는다.
      같은 세계관의 얼굴 문법을 지키되 모든 캐릭터의 얼굴 비례를 같게 만들지 않는다.
      귀·지느러미·날개가 해부 구조라면 몸의 일부로 정의한다.
      생명감과 표정이 있는 동반자를 만든다. 관광 물건에 얼굴만 붙이지 않는다.
      내부 빛은 운전 점수·위험도·희귀도 지표가 아니다.
      화자 ID, provider URL, 운전 평가, finalText는 생성하지 않는다.
```

모델의 novelty 설명은 평가 결과가 아니다. 실제 descriptor 비교와 이미지·사람의 구별 평가를 별도로 수행한다. 모델이 catalog에 없는 rig를 제안한 경우 제작 후보로만 남기고 준비 완료로 처리하지 않는다.

## 일러스트레이션 프롬프트

```text
Use case: stylized-concept.
Asset type: one Nunti journey-born companion, neutral master illustration.
Reference: user-selected C image is the art-world reference, not an instruction
to copy the same face and silhouette for every new being.
Subject: {selectedCharacterRecipe}.
Style: cohesive 2.5D illustration, softly frosted translucent resin volumes,
opaque cream face, restrained internal motifs, diffused inner light,
rounded forms, satin edges, limited pearlescent highlights.
Composition: full body, fixed front three-quarter camera, generous clear margin,
quiet neutral pose, no cropped ears or feet, readable silhouette at small size.
Character identity: preserve the recipe's body topology, face proportions,
asymmetry and signature motif. Place the face directly on the body.
Constraints: no costumes as the only novelty, no sharp crystals, glitter clutter,
photorealistic caustics, typography, logos, UI, or franchise resemblance.
Background: request genuine alpha when producing a cutout. A concept plate's
ivory backdrop is not a production alpha asset.
```

표정 변형은 선택한 master 이미지를 참조해 하나씩 만든다. change only expression을 명시하고 몸체·얼굴 기준점·재질·내부 무늬·카메라·광원은 유지한다. 여섯 표정을 독립 신규 생성해 같은 캐릭터라고 가정하지 않는다. 투명 출력은 생성 도구에 실제 alpha를 요청하고 결과를 확인한다.

## 레이어·동작 제작 프롬프트

```text
역할: 선택 캐릭터의 2.5D 리깅·동작 제작자.
입력: 확정 master, 여섯 표정 참조, rig family manifest.
과제: 외피 뒤/내부 모티브/몸체 앞/얼굴/하이라이트/접지 그림자를
      분리하는 제작 계획과 검증 가능한 asset manifest를 만든다.
유지: 같은 silhouette, face-safe 영역, 색·재질, 앵커와 레이어 순서.
동작 후보: 주차 화면의 짧은 눈깜박임, 미세 호흡, 인사.
제약: 변형 중 몸 구조·귀 개수·얼굴 비례가 바뀌지 않는다.
      원본에 숨겨진 부위를 임의 생성한 경우 새 자산으로 검수한다.
      모델이 만든 계획을 레이어 파일·rig 제작 완료로 표시하지 않는다.
      주행 표시 정책이 차단하면 정적 자산도 숨긴다.
출력: 파일 역할·alpha·좌표·pivot·anchor·expression ID·버전·호환 규격,
      누락 자산과 수작업 보완 목록. 실제 파일 digest는 제작 후 계산한다.
```

첫 단계는 정적 6표정이다. 매 여행 새 영상을 생성하는 방식을 기본으로 삼지 않는다. 동작 중 identity 일치와 취소·표시 정책 검증이 가능한 작은 rig부터 확인한다. 현재 앱은 새 레이어와 동작을 지원하지 않는다.

## 목소리를 고르는 프롬프트

```text
역할: 한국어 캐릭터 음성 캐스팅 보조자.
입력: personality, body/material/interior traits, 검수된 voice catalog,
      각 후보의 실제 청취 결과와 확인된 controls.
출력: 허용 candidate ID 하나, 선택 이유, catalog에 존재하는 preset ID.
규칙: 알 수 없는 화자 ID·emotion/rate/pitch 제어를 만들어내지 않는다.
      반투명 재질을 무조건 고음·속삭임·잔향으로 표현하지 않는다.
      같은 캐릭터의 새 문장도 저장된 voice binding을 사용한다.
      사용할 후보가 없으면 UNBOUND를 반환한다.
      승인 텍스트와 finalText의 문자·공백·의미를 바꾸지 않는다.
```

실제 발음·귀여움·외형 적합성·같은 화자로 들리는지는 청취자가 평가한다. 목소리 설명만 다른 상태를 실제 음색 변화로 보고하지 않는다. 모델은 발화 허가나 재생을 실행하지 않는다.

## 품질을 비평하는 프롬프트

```text
역할: 제작팀과 독립적인 캐릭터 품질 검토자.
입력: 같은 입력의 후보 이미지, 최근 컬렉션, master와 표정들,
      밝은/어두운 배경의 64px·128px 출력, 레이어 검사 결과, 실제 음성 표본.
출력: 얼굴 가독성, 몸체 구별, 세계관 일관성, 표정 identity,
      반투명 경계/레이어 결함, 외형·음성 적합성에 대해 PASS/FAIL/UNTESTED와 근거.
규칙: 없는 표정·작은 화면·음원을 상상해 통과시키지 않는다.
      해시·ID 차이를 시각적 개별성으로 인정하지 않는다.
      귀여움·소장 의향의 사용자 평가를 대체하거나 운전습관 개선을 보장하지 않는다.
```

자동 검토의 PASS 뒤에도 사람의 품질 평가가 필요하다. 현재 시안은 단일 정적 이미지로만 확인했다. 실제 작은 화면·표정·rig·음성 표본이 없어 해당 항목은 UNTESTED다.
