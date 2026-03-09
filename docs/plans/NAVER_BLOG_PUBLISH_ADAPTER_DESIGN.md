# Naver Blog Publish Adapter Design

## 목적

`MubloOps`에서 작성된 초안에 포함된 `[[IMAGE:id]]` 슬롯과 로컬 이미지를 이용해, 네이버 블로그에 실제 이미지 포함 게시글을 자동 발행할 수 있는 구조를 설계한다.

이 문서는 구현 전에 반드시 봐야 하는 기준 문서다.

## 전제

- writer 본문에는 최종 외부 이미지 URL이 아니라 `[[IMAGE:id]]` 슬롯만 저장한다.
- 실제 이미지 업로드는 publish 단계에서 수행한다.
- 네이버 블로그는 WordPress/Tistory보다 제약이 크므로, 네이버 기준으로 공통 구조를 설계한다.

## 현재 상태

이미 준비된 것:

- 로컬 다운로드 이미지 저장
  - `RawImage.local_path`
- 로컬 이미지 미리보기 URL
  - `/api/collected/images/{id}/file`
- writer 본문 이미지 슬롯
  - `[[IMAGE:id]]`
- generation 메타 저장
  - `generated_articles.generation_meta_json`

아직 없는 것:

- 네이버 블로그 로그인/세션 관리
- 네이버 블로그 에디터 조작 adapter
- 로컬 이미지 업로드 후 본문 삽입 로직
- 발행 실패 복구 로직

## 핵심 설계 원칙

1. 네이버는 별도 adapter로 분리한다
- WordPress/Tistory와 같은 publish 함수 안에 if 문으로 섞지 않는다.

2. 인증과 발행을 분리한다
- 로그인/세션 확보 단계
- 글쓰기/이미지 업로드/발행 단계

3. 이미지 업로드는 본문 렌더링 전에 완료한다
- `[[IMAGE:id]]` 슬롯을 실제 블로그 에디터 이미지 블록으로 바꾸려면 업로드 결과가 먼저 필요하다.

4. 실패를 세분화해 기록한다
- 로그인 실패
- 세션 만료
- 이미지 업로드 실패
- 본문 삽입 실패
- 임시저장 실패
- 최종 발행 실패

5. 완전 무인 자동화보다 운영 가능한 반자동 구조를 우선한다
- 필요 시 사용자가 로그인만 수동으로 해주고
- 이후 발행은 자동으로 이어가는 구조도 허용한다.

## 우선 가정

현재 가장 현실적인 경로는 `Selenium 기반 브라우저 자동화`다.

이유:

- 네이버 블로그는 공개적이고 안정적인 발행 API 전제가 약하다.
- 이미지 업로드와 스마트에디터 조작은 브라우저 기반 흐름이 더 현실적이다.
- 현재 프로젝트도 수집에서 실제 브라우저 기반 흐름을 이미 사용하고 있다.

즉 1차 설계는 아래 기준으로 한다.

- 엔진: Selenium
- 브라우저: Chrome 또는 Edge
- 실행 방식: 사용자 PC 로컬 실행
- 세션 저장: 로컬 profile 또는 쿠키 저장

## 사용자 제공 정보

최소 필요:

- 네이버 계정 아이디
- 네이버 계정 비밀번호
- 발행 대상 블로그 식별 정보

추가로 필요한 항목:

- 2차 인증 사용 여부
- 캡차/추가 인증 발생 시 수동 개입 허용 여부
- 브라우저 프로필 재사용 여부
- 발행 대상이 단일 블로그인지 다중 블로그인지

설정 화면에서 받을 후보:

- `naver.username`
- `naver.password_ref`
- `naver.blog_id`
- `naver.use_saved_profile`
- `naver.profile_path`
- `naver.headless`
- `naver.manual_login_allowed`

중요:

- 비밀번호 평문 저장은 지양
- 최소한 alias 또는 로컬 암호 저장소 참조 구조 필요

## 권장 아키텍처

### 1. 구성 요소

#### `NaverSessionManager`
- 로그인 상태 확인
- 쿠키/프로필 재사용
- 세션 만료 판단
- 필요 시 로그인 수행

#### `NaverImageUploader`
- `RawImage.local_path` 기반 이미지 업로드
- 업로드 결과를 editor insertion handle로 변환
- 업로드 실패/재시도 관리

#### `NaverEditorAdapter`
- 스마트에디터 열기
- 제목 입력
- 본문 블록 삽입
- 이미지 블록 삽입
- 임시저장 / 발행 버튼 처리

#### `NaverPublishAdapter`
- article 로드
- 슬롯 추출
- 이미지 업로드
- 본문 렌더링
- editor adapter 호출
- 최종 결과 기록

### 2. 데이터 흐름

1. `GeneratedArticle.content` 로드
2. `[[IMAGE:id]]` 슬롯 추출
3. 각 `id`에 대해 `RawImage.local_path` 확보
4. 세션 유효성 확인
5. 에디터 진입
6. 제목 입력
7. 텍스트 블록 입력
8. 이미지 슬롯 위치마다 해당 이미지 업로드/삽입
9. 발행 또는 임시저장
10. 결과 기록

## 본문 렌더링 방식

네이버 블로그는 1차에서 `HTML 치환`보다 `블록 단위 재생성`이 더 안전하다.

즉 발행 시에는 저장된 원문을 그대로 붙여넣는 것이 아니라 아래처럼 해석한다.

- 일반 텍스트 문단
- markdown heading
- `[[IMAGE:id]]`

이 세 가지를 editor block으로 분해해 입력한다.

### 권장 파서 규칙

- `#`, `##`, `###` -> 제목/소제목 블록
- 빈 줄 기준 -> 문단 구분
- `[[IMAGE:id]]` -> 이미지 블록

즉 네이버 발행 직전에는:

- `article.content` 문자열
- `content_blocks[]`

형태로 한 번 변환해서 에디터에 순차 입력한다.

## 이미지 업로드 설계

### 입력

- `raw_image_id`
- `local_path`
- `caption`
- 위치 정보

### 출력

네이버 특성상 정확한 remote URL보다 아래 수준의 결과가 더 현실적일 수 있다.

- 에디터 삽입 성공 여부
- 내부 업로드 응답 객체 일부
- 첨부 순번
- 스크린샷/로그

따라서 1차는 `업로드 URL 저장`보다 아래 정보를 남기는 쪽이 좋다.

- `raw_image_id`
- `upload_status`
- `inserted_order`
- `error_message`

## 세션 관리 설계

### 전략 A. 브라우저 프로필 재사용

장점:

- 로그인 유지가 쉬움
- 2차 인증 반복을 줄일 수 있음

단점:

- 사용자 PC 환경 의존
- profile 충돌 가능

### 전략 B. 쿠키 저장/복원

장점:

- 앱이 제어하기 쉬움

단점:

- 네이버는 세션 보안이 강해서 깨질 가능성 있음

### 결론

1차는 `브라우저 프로필 재사용`이 더 현실적이다.

권장 정책:

- 사용자가 최초 1회 로그인
- 앱은 해당 profile을 재사용
- 세션 만료 시 수동 로그인 유도

## 실패 처리 정책

### 로그인 실패

- 즉시 작업 중단
- 사용자에게 재로그인 필요 메시지
- 계정 잠금 위험이 있으므로 반복 재시도 제한

### 이미지 일부 업로드 실패

- 실패 슬롯만 건너뛰고 텍스트 발행 계속할지 정책 필요
- 기본은 `본문 이미지 일부 실패 시 경고 후 계속`

### 제목/본문 입력 실패

- 임시저장 시도
- 실패 로그 저장
- 발행 완료 처리 금지

### 최종 발행 실패

- 가능하면 임시저장 상태 확인
- 재시도 전에 수동 검토 필요 상태로 전환

## 필요한 저장/로그 구조

권장 신규 테이블 또는 로그 구조:

### `naver_publish_sessions`
- account_ref
- profile_path
- last_login_at
- last_validated_at
- status

### `publish_image_assets`
- article_id
- raw_image_id
- target_channel
- upload_status
- inserted_order
- remote_ref
- error_message
- updated_at

### `publish_run_logs`
- stage
- article_id
- target_channel
- step
- message
- screenshot_path
- created_at

## UI/설정 요구사항

필수:

- 네이버 계정 설정
- 프로필 경로 설정
- 수동 로그인 버튼
- 세션 확인 버튼
- 테스트 발행 버튼
- 이미지 업로드 테스트 버튼

권장:

- 마지막 세션 상태 표시
- 최근 실패 사유 표시
- 마지막 스크린샷 보기

## 단계별 구현 순서

### Step 1. 세션 검증기
- 브라우저 실행
- 로그인 상태 확인
- 프로필 재사용 확인

### Step 2. 글쓰기 진입 adapter
- 새 글 작성 페이지 진입
- 제목/본문 입력만 성공시키기

### Step 3. 단일 이미지 업로드
- 로컬 파일 1장 업로드
- 본문 삽입 성공 확인

### Step 4. 슬롯 기반 본문 렌더링
- `[[IMAGE:id]]`를 위치대로 삽입

### Step 5. 최종 발행/임시저장
- 발행 또는 임시저장 선택

### Step 6. 실패 복구와 로그
- 스크린샷, 단계 로그, 상태 저장

## 구현 전에 결정해야 할 질문

1. 네이버 계정 로그인 정보를 어떤 방식으로 저장할 것인가
2. 브라우저 profile 재사용을 강제할 것인가
3. headless를 허용할 것인가
4. 이미지 일부 실패 시 발행을 중단할 것인가
5. 임시저장 우선 후 발행으로 갈 것인가

## 권장 결론

현재 기준 권장안:

- 1차는 `Selenium + 사용자 브라우저 프로필 재사용`
- `임시저장 성공 -> 최종 발행` 2단계 흐름
- 이미지 슬롯은 HTML 변환이 아니라 `에디터 블록 삽입`
- 로그인 실패/세션 만료는 수동 개입 허용

이 결론을 기준으로 해야 이후 코드 계획이 흔들리지 않는다.

## 다음 문서

- [Naver Blog Publish Next Step](/D:/Project/MubloOps/docs/plans/NAVER_BLOG_PUBLISH_NEXT_STEP.md)
- [Writer Body And Image Refactor Plan](/D:/Project/MubloOps/docs/plans/WRITER_BODY_AND_IMAGE_REFACTOR_PLAN.md)
