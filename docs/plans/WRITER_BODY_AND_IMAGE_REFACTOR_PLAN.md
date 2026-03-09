# Writer Body And Image Refactor Plan

## 목표

발행용 글 본문을 내부 작성 메타와 분리하고, 수집된 이미지 자산을 실제 글 작성에 반영한다.

추가 기준:

- 이미지 자산은 가능하면 외부 원본 URL이 아니라 이미 다운로드된 `local_path` 기준으로 사용한다.
- writer, 보기 화면, 발행 경로가 같은 이미지 자산 식별자를 공유해야 한다.

## 우선순위

### Phase 1. 내부 메타와 발행 본문 분리

목표:

- `[작성 채널]`, `[SEO 패턴 가이드]` 같은 내부 블록이 `article.content`에 저장되지 않게 한다.

작업:

- `writer.service`에서 `_prepend_seo_notes()`, `_prepend_channel_notes()` 방식 제거
- 내부 메타는 별도 필드나 JSON 메타로 저장
- `article.content`에는 발행용 순수 본문만 저장
- 보기 화면에서는 필요 시 `내부 가이드 보기`로 별도 렌더
- 발행 경로는 항상 순수 본문만 사용

권장 구현:

- `generated_articles`에 `generation_meta_json` 추가
- 저장 예시:
  - `seo_strategy`
  - `seo_metrics`
  - `channel_name`
  - `channel_type`
  - `source_ids`
  - `image_ids`

### Phase 2. writer 입력 데이터 확장

목표:

- writer가 텍스트 요약만이 아니라 원문 본문과 이미지 자산까지 받을 수 있게 한다.

작업:

- `RawContentDTO` 확장:
  - `body_text`
  - `body_html`
  - `author`
- writer 전용 이미지 DTO 추가:
  - `image_id`
  - `content_id`
  - `local_path`
  - `local_url`
  - `image_url`
  - `thumbnail_score`
  - `text_overlay`
  - `is_thumbnail_candidate`
- `CrawlRepository.list_recent_contents_for_writer()`에서 원문/이미지 묶음 반환
- `CrawlRepository.get_contents_by_ids()`도 같은 구조로 확장

로컬 이미지 기준 추가 작업:

- writer 전용 조회에서 `RawImage.local_path`가 있는 이미지만 우선 사용
- 웹 셸에서 이미 제공 중인 `/api/collected/images/{id}/file` 경로를 `local_url`로 같이 전달
- writer는 외부 URL 대신 `image_id + local_url`을 기준으로 이미지 계획을 세움
- 발행 직전까지는 로컬 이미지 참조를 유지하고, 채널 업로드 단계에서만 실제 업로드/변환 수행

### Phase 3. 이미지 선택 로직 추가

목표:

- 수집 이미지 중 실제 글에 넣을 후보를 정한다.

작업:

- 이미지 후보 선별 규칙 정의
  - `local_path IS NOT NULL` 우선
  - `thumbnail_score` 높은 순
  - `text_overlay=False` 우선
  - 너무 작은 이미지 제외
  - 동일 source_url 중복 제외
- 본문-이미지 연관성 규칙 추가
  - 같은 `content_id`에 속한 이미지를 먼저 사용
  - 해당 원문 이미지가 부족하면 같은 `keyword_id`의 최근 이미지로 확장
  - 채널 믹스가 과하면 제외
- 채널별 이미지 정책 반영
  - wordpress/tistory: 본문 이미지 허용
  - naver_blog: 본문 이미지 수 제한 가능
- 대표 이미지 1장 + 본문 이미지 N장 구조로 선택

권장 선택 전략:

1. 대표 이미지 1장:
   - `is_thumbnail_candidate=True` 우선
   - 동률이면 `thumbnail_score` 높은 순
2. 본문 이미지:
   - `text_overlay=False`
   - 같은 원문에서 나온 이미지 우선
   - 소제목 수보다 많으면 상위 점수 이미지만 남김
3. 제외:
   - `local_path` 없는 항목
   - 중복 source_url
   - 너무 작은 파일 또는 손상 파일

### Phase 4. 템플릿/프롬프트 개편

목표:

- 모델이 이미지와 본문 구조를 함께 생성하게 만든다.

작업:

- 템플릿 변수 추가
  - `{{source_outline}}`
  - `{{image_plan}}`
  - `{{image_slots}}`
- writer 입력에 실제 이미지 후보를 함께 제공
  - `image_id`
  - `caption_hint`
  - `placement_hint`
  - `local_url`
- 프롬프트에 명시
  - 본문 내부에 이미지 위치를 소제목 사이에 배치
  - HTML 허용 채널은 `<img>` 또는 이미지 슬롯 마커 생성
  - 이미지가 없으면 억지로 넣지 않음

권장 출력 방식:

- 1안: writer가 `[[IMAGE:raw_image_id]]` 같은 슬롯 마커를 생성
- 2안: 후처리에서 적절한 소제목 뒤에 자동 삽입

현재 프로젝트에는 1안이 더 안전하다.

로컬 이미지 기준 상세:

- writer는 이미지 본문 자체를 직접 base64로 들고 가지 않는다.
- writer는 아래처럼 "삽입 가능한 로컬 이미지 슬롯 목록"만 받는다.
  - `[[IMAGE:123]] - 설치 전경`
  - `[[IMAGE:124]] - 제품 클로즈업`
- 생성 결과에는 슬롯 마커만 들어가고, 실제 `<img>` 태그/업로드 처리는 후처리에서 담당한다.

### Phase 5. 후처리/발행 전 변환

목표:

- 작성 결과를 채널별 발행 포맷으로 정리한다.

작업:

- 이미지 슬롯 마커를 실제 HTML/블록으로 변환
- 채널별 허용 마크업에 맞게 변환
- 본문 내 내부 제어 텍스트 제거 보장
- SEO 검수도 순수 본문 기준으로만 수행

로컬 이미지 후처리 전략:

- 보기 화면:
  - `[[IMAGE:id]]`를 `/api/collected/images/{id}/file` 미리보기로 렌더
- wordpress/tistory:
  - 발행 직전 로컬 파일을 채널 API에 업로드
  - 업로드 후 반환된 미디어 URL로 본문 치환
- naver_blog:
  - 초기 단계에서는 이미지 슬롯을 제거하거나 별도 업로드 모듈 준비 전까지 텍스트만 발행
  - 이후 전용 업로드 모듈이 생기면 동일한 방식으로 치환

중요 정책:

- writer DB 본문에는 외부 최종 URL이 아니라 `[[IMAGE:id]]` 같은 중립 슬롯을 저장
- 실제 채널 URL은 발행 시점에만 확정
- 이렇게 해야 재발행/재생성/미리보기가 모두 안정적이다

### Phase 6. 자동 발행용 블로그 이미지 등록

목표:

- 선택된 로컬 이미지를 자동 발행 시 각 블로그 채널에 실제 미디어로 등록하고, 본문의 이미지 슬롯을 채널별 최종 URL/블록으로 치환한다.

핵심 원칙:

- 이미지 업로드는 writer 단계가 아니라 publish 단계에서 수행
- 업로드 결과는 매번 재사용할 수 있게 기록
- 채널마다 업로드 방식이 다르므로 공통 인터페이스 + 채널별 adapter 구조로 구현

필요 저장 구조:

- `publish_image_assets` 같은 테이블 또는 JSON 매핑
  - `article_id`
  - `raw_image_id`
  - `target_channel`
  - `local_path`
  - `upload_status`
  - `remote_media_id`
  - `remote_url`
  - `last_uploaded_at`
  - `error_message`

공통 처리 순서:

1. 발행 직전 `article.content`에서 `[[IMAGE:id]]` 슬롯 추출
2. 각 `raw_image_id`의 `local_path` 유효성 검사
3. 채널 adapter로 이미지 업로드
4. 업로드 성공 시 `remote_media_id`, `remote_url` 저장
5. 본문 슬롯을 채널별 최종 마크업으로 치환
6. 최종 본문 + 대표 이미지 정보로 게시글 발행

#### WordPress 계획

업로드 방식:

- WordPress REST API media endpoint 사용
- 일반적으로 `/wp-json/wp/v2/media`

처리:

- 로컬 파일 multipart 업로드
- 응답에서 `id`, `source_url` 확보
- 대표 이미지 1장은 `featured_media`로 연결
- 본문 이미지 슬롯은 `<figure><img ...></figure>` 또는 기본 `<img>` 태그로 치환

추가 설정:

- `api_endpoint_url`
- 인증 방식
- 대표 이미지 사용 여부
- alt text 생성 규칙

캐시 전략:

- 같은 article 재발행 시 이미 업로드된 media id가 있으면 재업로드하지 않고 재사용 가능

#### Tistory 계획

업로드 방식:

- Tistory Open API의 attach/upload 계열 사용 전제
- 최종 구현 시 실제 API 스펙 확인 필요

처리:

- 로컬 파일 업로드 후 첨부 식별자 또는 URL 확보
- 본문 슬롯을 Tistory 허용 HTML 또는 첨부 마크업으로 치환
- 대표 이미지가 필요하면 첫 이미지 또는 최고 점수 이미지를 대표로 사용

주의:

- 티스토리는 본문 이미지 마크업 규칙이 워드프레스보다 제한적일 수 있음
- 업로드 후 반환 포맷에 맞춰 전용 치환기 필요

#### Naver Blog 계획

업로드 방식:

- 현재는 자동 이미지 업로드 모듈 없음
- 네이버 블로그는 에디터/세션 기반 제약이 있어 별도 adapter 필요

단계별 계획:

1. 1차:
   - 자동 발행 시 이미지 슬롯 제거 또는 텍스트 발행
2. 2차:
   - Selenium/브라우저 기반 업로드 흐름 추가
   - 임시 업로드 -> 에디터 삽입 -> 게시까지 한 흐름으로 연결

주의:

- 네이버는 API 안정성보다 브라우저 자동화 의존 가능성이 높음
- 따라서 `naver_blog`는 별도 실험/운영 플래그를 두는 것이 안전

### Phase 7. 발행 adapter 구조

목표:

- 채널별 이미지 업로드/본문 치환을 공통된 publish 파이프라인으로 묶는다.

권장 인터페이스:

- `prepare_images(article, target_channel) -> uploaded_assets`
- `render_body(article, uploaded_assets, target_channel) -> final_body`
- `publish_article(article, final_body, target_channel, featured_asset)`

채널별 adapter 예시:

- `WordPressPublishAdapter`
- `TistoryPublishAdapter`
- `NaverBlogPublishAdapter`

공통 fallback:

- 이미지 업로드 실패 시
  - 대표 이미지만 실패: 대표 이미지 없이 진행 가능 여부 판단
  - 본문 이미지 일부 실패: 해당 슬롯만 제거 후 계속 진행
  - 전부 실패: 채널 정책에 따라 중단 또는 텍스트만 발행

### Phase 8. 로컬 이미지 자산 검증

목표:

- 다운로드된 이미지가 실제로 쓸 수 있는 상태인지 선별한다.

작업:

- 파일 존재 여부 검사
- 손상 파일 검사
- 최소 해상도/파일 크기 기준 추가
- MIME 타입 확인
- 로컬 파일 누락 시 fallback 정책 정의

권장 fallback:

- 대표 이미지만 없으면 텍스트 글로 계속 진행
- 본문 이미지가 부족하면 남은 슬롯은 제거
- 외부 원본 URL 재사용은 기본적으로 하지 않음

## 추가 정리 과제

### SEO 패턴 정제

문제:

- 커뮤니티/플랫폼 UI 텍스트가 `common_sections`, `common_terms`에 섞임

작업:

- 사이트 크롬성 용어 stoplist 추가
- `갤러리`, `닫기`, `차단하기`, `부매니저` 같은 UI 단어 제거
- 본문 구조와 탐색 요소를 분리하는 rule 강화

### 재생성 정책

현재:

- 같은 article id를 유지하면서 덮어씀

추가 검토:

- `published` 글은 재생성 금지 유지
- 필요 시 `복제 후 재생성` 옵션 추가

## 다음 작업 순서

1. `generation_meta_json` 추가
2. writer 본문에서 내부 가이드 prepend 제거
3. writer 입력 DTO에 본문/로컬 이미지 자산 추가
4. 로컬 이미지 검증 + 이미지 선택기 구현
5. `[[IMAGE:id]]` 슬롯 기반 프롬프트/후처리 추가
6. 보기 화면에서 로컬 이미지 슬롯 렌더
7. 발행 이미지 자산 매핑 저장 구조 추가
8. WordPress 이미지 업로드/치환 구현
9. Tistory 이미지 업로드/치환 구현
10. Naver Blog 이미지 발행 전략 분리
11. SEO 패턴 stoplist 정제

## 완료 기준

- 발행 대상 본문에 내부 가이드 문구가 없어야 함
- 작성 결과에 로컬 이미지 슬롯이 실제로 반영되어야 함
- 보기 화면에서 로컬 이미지가 실제로 보여야 함
- 발행 시 로컬 이미지가 채널 포맷에 맞게 치환되어야 함
- 자동 발행 시 채널별 업로드 결과가 추적 가능해야 함
- 보기 화면과 발행 화면이 동일한 순수 본문을 기준으로 해야 함
- SEO 검수는 내부 메타가 아닌 실제 본문만 평가해야 함
