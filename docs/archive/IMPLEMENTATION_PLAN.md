# BlogWriter 실제 개발 실행 계획서

## 1. 개발 전제
- 본 프로젝트는 **신규 구현(그린필드)** 로 진행한다.
- 결제/과금/라이선스 기능은 현재 범위에서 제외한다.
- 배포 타겟은 Windows EXE 단일 앱이다.
- 웹서버 없이 동작하는 데스크톱 앱을 기본으로 한다.

## 2. 최종 산출물(MVP)
- 카테고리/키워드/채널 설정이 가능한 수집 시스템
- 텍스트/이미지 라벨링 저장
- 페르소나 기반 글 생성(블로그/SNS/게시판)
- 에디터 기반 검수/수정
- 반자동 발행 + 자동 발행 스케줄러
- EXE 설치/실행 가능 패키지

## 3. 기술 스택 확정
- Language: Python 3.12
- UI: Pyside6 (화면 90% 기본)
- DB: SQLite + SQLAlchemy + Alembic
- Crawl: requests + bs4 + selenium(선택)
- AI: OpenAI/Gemini 추상화 어댑터
- Image: Pillow
- Build: PyInstaller
- Test: pytest

## 4. 프로젝트 구조(실제 생성 대상)
- `blogWriter/src/app` (앱 부트스트랩, DI)
- `blogWriter/src/core` (도메인 모델, 공통 정책)
- `blogWriter/src/collector` (채널 크롤러)
- `blogWriter/src/labeling` (텍스트/이미지 라벨러)
- `blogWriter/src/writer` (페르소나, 프롬프트, 생성기)
- `blogWriter/src/publisher` (발행 어댑터, 스케줄러)
- `blogWriter/src/ui` (화면/컴포넌트/에디터)
- `blogWriter/src/storage` (ORM, 리포지토리, 마이그레이션)
- `blogWriter/tests`
- `blogWriter/build`
- `blogWriter/docs`

## 5. 작업 단계 및 일정(10주)
## Week 1: 기반 세팅
- 리포지토리 구조 생성
- Python 환경/의존성/코딩 규칙 설정
- SQLAlchemy + Alembic 초기화
- 앱 실행 골격(Pyside6 메인 윈도우 90% 크기)

완료 기준:
- 앱 실행/종료 가능
- 기본 DB 마이그레이션 실행 성공

## Week 2: 데이터 모델 + 설정 화면
- 핵심 테이블 구현(categories, keywords, contents, images, personas, articles, publish_jobs)
- 카테고리/키워드/채널 설정 UI
- 설정 저장/불러오기

완료 기준:
- 설정 CRUD 동작
- DB 스키마 문서 자동 생성

## Week 3-4: 수집 파이프라인
- 채널 어댑터 인터페이스 구현
- 네이버/티스토리 수집기 1차 구현
- 중복 제거/실패 재시도/로그 처리
- 이미지 로컬 저장 + 메타 저장

완료 기준:
- 키워드 실행 시 콘텐츠/이미지 저장 성공
- 실패 건 재시도 가능

## Week 5: 라벨링
- 텍스트 라벨러(rule)
- 이미지 라벨러(rule)
- 라벨 검수 UI + 수동 수정 기능

완료 기준:
- 미라벨링 데이터 일괄 처리 가능
- 라벨 수정 이력 저장

## Week 6-7: 글 생성 + 에디터
- 페르소나 CRUD UI (다중 페르소나 생성/수정/삭제/활성화)
- 형식별 생성기(블로그/SNS/게시판)
- Rich Editor + Markdown 미리보기 + 이미지 삽입
- 생성 초안 저장/버전 복원

완료 기준:
- 페르소나 2개 이상 등록 후 선택 기반 3가지 형식 글 생성 가능
- 에디터에서 저장/복원 가능

## Week 8: 발행 프로세스
- 반자동 발행 워크플로우(승인 -> 발행)
- 자동 발행 스케줄러(시간/조건 기반)
- 발행 로그/실패 큐/재시도

완료 기준:
- 반자동/자동 발행 모두 동작
- 실패 내역에서 재시도 가능

## Week 9: 안정화/테스트
- 통합 테스트 시나리오 작성
- 대량 데이터 테스트(성능/메모리)
- 예외 처리, 복구, 백업/복원 점검

완료 기준:
- 핵심 시나리오 테스트 통과율 95%+

## Week 10: 배포
- PyInstaller 빌드 스크립트
- 실행파일/리소스 패키징
- 설치/업데이트/문서 정리

완료 기준:
- 새 PC에서 설치 후 즉시 실행 가능

## 6. 개발 방식(실행 규칙)
- 브랜치 전략: `main` + `dev` + feature 브랜치
- 커밋 규칙: `feat|fix|refactor|test|docs`
- PR 단위: 1기능 1PR 원칙
- 모든 기능은 테스트 최소 1개 이상 포함

## 7. Definition of Done (DoD)
- 기능 요구사항 충족
- 예외/오류 메시지 처리 완료
- DB 마이그레이션 포함
- 테스트 통과
- 사용자 문서(짧은 사용법) 업데이트

## 8. 테스트 계획
- Unit: 라벨러, 생성기, 파서, 정책 로직
- Integration: 수집->라벨링->생성->발행 파이프
- UI: 핵심 플로우 수동 테스트 체크리스트
- Regression: 이전 데이터 열기/편집/발행

## 9. 리스크와 선대응
- 수집 채널 구조 변경: 어댑터 분리 + 빠른 핫픽스
- AI 응답 품질 편차: 템플릿 강제 + fallback 룰
- 앱 프리징: 비동기 작업 큐 + 진행 상태 표시
- 데이터 손실: 자동 백업 + 복구 마법사

## 10. 첫 구현 태스크(바로 착수)
1. `blogWriter/src` 기본 디렉토리 생성
2. `pyproject.toml`/`requirements.txt` 작성
3. Pyside6 메인 윈도우 + 90% 크기 정책 구현
4. SQLite 연결 + 초기 마이그레이션 생성
5. 카테고리/키워드 CRUD 최소 화면 구현

## 11. 진행 보고 방식
- 일일 보고: 완료/진행/블로커 3줄
- 주간 보고: 기능 데모 + 다음 주 계획
- 이슈 발생 시: 원인/영향/대응/예상 일정 즉시 공유
