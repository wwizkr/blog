# MubloOps Handoff - 2026-03-07 Writer Review

## 오늘 작업 요약

- 작성 결과 목록에 `수정` 기능을 추가했다.
- 작성 결과 목록과 수정 모달에 `재생성` 기능을 추가했다.
- 재생성은 같은 글 id를 유지한 채 제목/본문을 다시 생성하고 `draft` 상태로 되돌린다.
- `generated_articles`에 `writing_channel_id`, `ai_provider_id`를 저장하도록 보강했다.
- 작성 결과 목록에 `보기` 버튼을 추가했다.
- 수정 모달의 본문 입력창을 별도 스타일의 plain textarea로 바꿔 가독성을 높였다.

## 확인한 현재 상태

### 1. 실제 AI 생성은 동작함

- `writer.service.generate_draft()`는 현재 OpenAI/Gemini provider를 호출해 실제 본문을 생성한다.
- 재생성도 같은 경로를 사용한다.
- 최근 검증에서는 같은 article id를 유지한 채 재생성 후 본문 길이 약 3,100자 수준으로 갱신되는 것을 확인했다.

### 2. 내부 가이드가 실제 본문에 섞여 저장됨

현재 [src/writer/service.py](/D:/Project/MubloOps/src/writer/service.py)에서 아래 두 메서드가 생성 본문 앞에 직접 붙는다.

- `_prepend_seo_notes()`
- `_prepend_channel_notes()`

즉 아래와 같은 블록이 `article.content` 자체에 저장된다.

- `[작성 채널: ...]`
- `[SEO 패턴 가이드]`
- `전략 해석 ...`
- `정량 가이드 ...`

이 구조는 내부 작성 보조 메타와 발행용 본문이 분리되지 않은 상태다. 현재 그대로 발행 로직을 타면 이 블록이 노출될 가능성이 있다.

### 3. 이미지가 본문에 전혀 반영되지 않음

원인은 두 가지다.

#### 3-1. 작성 입력에 이미지 데이터가 안 들어감

[src/storage/repositories.py](/D:/Project/MubloOps/src/storage/repositories.py)의 `list_recent_contents_for_writer()`와 `get_contents_by_ids()`는 현재 아래 정보만 `RawContentDTO`로 넘긴다.

- `id`
- `keyword_id`
- `keyword`
- `channel_code`
- `title`
- `source_url`
- `created_at`

즉 writer는 원문 본문도 일부만 보고, 이미지 목록이나 로컬 이미지 경로를 전혀 전달받지 못한다.

#### 3-2. 프롬프트는 이미지 "개수"만 말하고 실제 삽입 자산은 주지 않음

[src/writer/service.py](/D:/Project/MubloOps/src/writer/service.py)의 `_build_seo_notes()`는 `권장 이미지 N개`까지만 만든다.

[src/storage/database.py](/D:/Project/MubloOps/src/storage/database.py)의 기본 템플릿도 현재는 아래 수준이다.

- `{{seo_strategy}}`
- `{{seo_metrics}}`
- `{{source_summary}}`

즉 모델에게는 "이미지 8개가 좋다"는 힌트만 있고,

- 어떤 이미지를 쓸지
- 어디에 넣을지
- HTML `<img>`를 넣을지
- 대표 이미지와 본문 이미지를 어떻게 구분할지

이 규칙이 없다.

### 4. SEO 패턴 해석 품질도 후처리 필요

현재 `seo_profile`은 상위 글 구조를 분석하지만, 커뮤니티 페이지 껍데기 요소가 섞인다.

예시:

- `연관 갤러리`
- `차단하기`
- `최근방문 갤러리`
- `부매니저`

이런 항목이 `common_sections`, `common_terms`로 저장되면 실제 작성 전략이 오염된다.

즉 SEO 프로파일은 동작하지만, `본문 콘텐츠 구조`와 `사이트 크롬/네비게이션 텍스트`를 더 잘 분리해야 한다.

## 오늘 기준 결론

현재 writer는 "초안 생성은 되는 상태"지만 아래 두 문제가 남아 있다.

1. 내부 메타와 발행 본문이 분리되지 않음
2. 이미지 자산이 작성 입력과 출력에 연결되지 않음

따라서 다음 작업 우선순위는 UX가 아니라 writer 파이프라인 정리다.

## 참고 구현 위치

- 작성 서비스: [src/writer/service.py](/D:/Project/MubloOps/src/writer/service.py)
- 결과 저장소: [src/storage/repositories.py](/D:/Project/MubloOps/src/storage/repositories.py)
- 웹 API: [src/ui/web_shell.py](/D:/Project/MubloOps/src/ui/web_shell.py)
- 작성 결과 UI: [src/ui/assets/web-shell/app.writer-run.js](/D:/Project/MubloOps/src/ui/assets/web-shell/app.writer-run.js)
- 기본 템플릿 시드: [src/storage/database.py](/D:/Project/MubloOps/src/storage/database.py)
