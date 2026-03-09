# Keyword Engine Expansion Plan

## 목적

현재 프로젝트의 키워드 수집은 네이버 연관검색어와 자동완성에 한정되어 있다.  
이 문서는 기존 버전을 유지한 상태에서, 별도 작업 디렉토리에서 키워드 수집부를 문서 `pipline.md`의 `Keyword Engine` 방향으로 확장하기 위한 설계 기준을 정의한다.

작업 복사본:
- `D:\Project\MubloOps`

원본 유지:
- `D:\Project\blogWriter`

메모:
- 복사본의 제품명은 `MubloOps`로 사용한다.

## 현재 상태 요약

### 현재 구현 위치
- `src/core/related_keyword_service.py`
- `src/collector/service.py`
- `src/collector/scheduler.py`
- `src/ui/web_shell.py`
- `src/storage/repositories.py`

### 현재 동작
- 연관 키워드 수집 소스는 사실상 네이버 1종이다.
- 수집 실행 후 `sync_from_naver()`가 호출된다.
- 생성된 키워드는 `keywords.is_auto_generated = true`로 저장된다.
- 관계 정보는 `keyword_related_relations.source_type`에 기록되지만 현재 실질적으로 `naver`만 사용한다.
- 수집 설정은 `keyword_scope`, `keyword_source_codes`, `related_keyword_limit` 수준에서 확장 중이다.

### 현재 한계
- 키워드 소스가 서비스 내부에 하드코딩되어 확장성이 낮다.
- `related_keyword_limit` 상한이 낮아 대량 롱테일 확장과 맞지 않는다.
- 소스별 우선순위, 활성화 여부, API 키, 쿼터 관리가 없다.
- 다단계 확장 깊이 제어가 없다.
- 수집 결과에 대한 품질 점수나 소스별 메타데이터가 없다.

## 목표

다음 조건을 만족하는 `Keyword Engine` 계층을 추가한다.

- 다중 키워드 소스를 지원한다.
- 소스별 on/off 및 설정 저장이 가능하다.
- 기존 네이버 연관키워드 기능은 하위 호환으로 유지한다.
- 수집 파이프라인과 느슨하게 결합한다.
- 추후 Google Suggest, Reddit, Quora, Amazon, SerpAPI, DataForSEO를 순차적으로 붙일 수 있어야 한다.

## 문서 기준 해석

`pipline.md` 기준으로 현재 프로젝트에서 당장 현실적으로 반영 가능한 범위는 다음이다.

1. Keyword Engine 다중 소스화
2. 롱테일 키워드 확장
3. 소스별 결과 정규화 및 중복 제거
4. 수집 설정과 실행 경로 분리

반면 아래 항목은 후속 단계로 분리한다.

1. Google People Also Ask 수집
2. SERP Analyzer
3. Competitor Content Extractor
4. Content Blueprint Generator
5. 외부 유료 API 연동의 운영 안정화

## 제안 아키텍처

### 1. Provider 기반 구조 도입

신규 계층 예시:

- `src/keyword_engine/base.py`
- `src/keyword_engine/providers/naver.py`
- `src/keyword_engine/providers/google_suggest.py`
- `src/keyword_engine/providers/reddit.py`
- `src/keyword_engine/service.py`

핵심 인터페이스 예시:

- `KeywordSourceProvider`
- `fetch(keyword: str, limit: int, context: dict) -> list[KeywordCandidate]`

공통 DTO 예시:

- `keyword`
- `source_type`
- `source_detail`
- `score`
- `raw_payload`

### 2. 현재 서비스와의 연결 방식

기존:
- `CrawlService.run_for_keyword()` 내부에서 `related_keyword_service.sync_from_naver()` 호출

변경:
- `CrawlService.run_for_keyword()` 내부에서 `keyword_engine_service.sync_related_keywords()` 호출
- 내부적으로 활성 provider들을 순회
- 결과를 병합, 정규화, 차단어 필터링 후 저장

### 3. 이행 원칙

- 기존 `related_keyword_service`는 단계적으로 제거할 수 있게 유지한다.
- 기준 설정은 `collect.keyword_source_codes`로 단일화한다.

## 데이터 모델 변경 계획

### 유지 가능한 기존 필드
- `keywords.is_auto_generated`
- `keyword_related_relations.source_type`

### 추가 권장 필드

`keyword_related_relations` 또는 신규 테이블로 다음 정보 저장 검토:

- `source_detail`
- `score`
- `first_seen_at`
- `raw_payload_json`

신규 설정 저장 키 예시:

- `collect.keyword_sources`
- `collect.keyword_source_limits`
- `collect.keyword_expand_depth`
- `collect.keyword_expand_total_limit`
- `collect.keyword_source_api_keys`

### DB 변경 우선순위

1. 설정 키 추가
2. 필요한 경우 관계 테이블 메타데이터 확장
3. 데이터 이관 없이 점진 적용

## 단계별 구현 계획

### Phase 1. 구조 분리

목표:
- 네이버 기능 유지
- 내부 구조만 provider 기반으로 재편

작업:
- `keyword_engine` 패키지 추가
- `NaverKeywordProvider` 구현
- 기존 `RelatedKeywordService`를 새 서비스 호출 구조로 변경
- `CrawlService`에서 신규 서비스 사용

완료 기준:
- 기존 네이버 연관키워드 수집 결과가 동일하게 동작한다.

### Phase 2. 설정 확장

목표:
- 소스별 활성화/비활성화 가능
- 한도값과 확장 깊이 설정 가능

작업:
- `CollectSettingKeys` 확장
- `/api/v2/settings/collect` 응답/저장 포맷 확장
- 웹 셸 수집 설정 UI에 키워드 소스 설정 추가

완료 기준:
- UI에서 네이버 on/off 및 제한값 조정 가능
- 이후 provider 추가 시 API 구조 변경 없이 수용 가능

### Phase 3. Google Suggest 추가

목표:
- 두 번째 provider를 실제 연결해 구조 검증

작업:
- `GoogleSuggestKeywordProvider` 구현
- 결과 정규화 규칙 추가
- 중복 제거 및 source_type 기록 검증

완료 기준:
- 동일 키워드에 대해 네이버 + 구글 제안어가 통합 저장된다.

### Phase 4. 확장 로직 개선

목표:
- 단순 단건 수집을 넘어 점진적 확장 가능

작업:
- 확장 깊이 1~N 설정
- 총 생성량 제한
- 품질 낮은 후보 제외 규칙
- 카테고리 기반 우선순위 또는 소스 우선순위 적용

1차 품질 필터 기준:
- 원본 키워드와 동일한 후보 제외
- 공백/구분자 정규화 후 중복 후보 제거
- 길이가 너무 짧은 후보 제외
- 기호만 남는 후보 제외

완료 기준:
- 지정된 상한 내에서 안정적으로 롱테일 키워드가 생성된다.

### Phase 5. 외부 API provider

후보:
- SerpAPI
- DataForSEO
- Naver-related API flow (replace unstable UI parsing in current `naver` provider)

작업:
- API 키 보관 정책 정의
- 호출 실패 및 쿼터 초과 대응
- 비용 통제용 일일 상한 추가

완료 기준:
- 외부 API가 선택적으로만 동작하고 미설정 시 시스템이 정상 유지된다.

### Naver 메모

- 현재 `naver` provider는 검색 UI/응답 구조 의존이 커서 0건이 나올 수 있다.
- 당장은 provider를 제거하지 않고 유지한다.
- 차후 내부 구현만 API 기반 수집으로 교체한다.
- 교체 시에도 `source_type = "naver"`는 유지해 기존 데이터/표시 호환을 보존한다.

## 코드 영향 범위

### 직접 수정 대상
- `src/core/related_keyword_service.py`
- `src/collector/service.py`
- `src/collector/scheduler.py`
- `src/core/settings_keys.py`
- `src/ui/web_shell.py`
- `src/ui/assets/web-shell/app.collect-settings.js`
- `src/ui/assets/web-shell/index.html`
- `src/storage/repositories.py`
- `src/storage/models.py`
- `migrations/versions/*`

### 신규 추가 대상
- `src/keyword_engine/`
- 필요 시 `tests/keyword_engine/`

## 리스크

### 1. 검색 소스 차단
- HTML 스크래핑 기반 provider는 마크업 변경이나 차단에 취약하다.

대응:
- provider별 예외 격리
- 소스 실패 시 전체 수집 실패로 번지지 않게 유지

### 2. 중복/저품질 키워드 증가
- 다중 소스 확장 시 유사 표현이 급격히 늘어날 수 있다.

대응:
- 공백/특수문자/접두어 정규화
- 소스별 score
- 차단 키워드 필터 강화

### 3. 성능 저하
- 수집 대상 키워드 수가 늘어나면 자동 수집 주기가 밀릴 수 있다.

대응:
- 총 확장량 상한
- provider별 타임아웃
- 후순위 provider 생략 정책

### 4. 설정 복잡도 증가
- UI가 지나치게 복잡해질 수 있다.

대응:
- 1차는 고급 설정 접기
- 기본값은 네이버만 활성화

## 검증 계획

### 기능 검증
- 단일 키워드 실행 시 연관키워드가 정상 저장되는지 확인
- 차단 키워드가 재등록되지 않는지 확인
- 기존 `related` 수집 모드가 정상 동작하는지 확인
- 신규 provider 추가 후 source_type이 분리 기록되는지 확인

### 회귀 검증
- 기존 수집 채널 콘텐츠 저장에 영향이 없는지 확인
- 자동 스케줄러가 예외 없이 유지되는지 확인
- 웹 셸 설정 저장/조회가 유지되는지 확인

### 운영 검증
- provider 실패 시 다음 키워드 처리 계속 진행
- API 키 미설정 시 graceful fallback 확인

## 권장 작업 순서

1. 복사본 디렉토리에서만 작업 진행
2. Phase 1 구조 분리
3. Phase 2 설정 확장
4. Phase 3 Google Suggest 추가
5. 안정화 후 외부 API provider 검토

## 이번 작업의 원칙

- 원본 프로젝트는 유지한다.
- 복사본에서만 키워드 엔진 구조 개편을 진행한다.
- 초기 목표는 기능 추가보다 구조 안정화다.
- 네이버 기능을 깨지 않는 범위에서 단계적으로 확장한다.
