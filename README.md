# BlogWriter

## 실행 방법
1. 가상환경 생성/활성화
2. 의존성 설치
   - `pip install -r requirements.txt`
3. 앱 실행
   - `set PYTHONPATH=src`
   - `python run.py`

## 현재 디렉토리 구조
```text
blogWriter/
├─ docs/
├─ migrations/
├─ src/
│  ├─ app.py
│  ├─ collector/
│  ├─ core/
│  ├─ labeling/
│  ├─ publisher/
│  ├─ storage/
│  ├─ ui/
│  └─ writer/
├─ tmp/
├─ run.py
└─ requirements.txt
```

## 메뉴 구조 (아코디언)
- 대시보드: 통합 현황, 단계별 상태
- 키워드 관리: 카테고리/키워드, 연관 키워드, 차단 키워드
- 수집: 수집 설정, 수집 실행, 작업 이력, 수집 데이터
- 라벨링: 라벨링 설정, 라벨링 실행, 라벨링 결과
- 글 작성: 글 작성 설정, 글 작성 실행, 페르소나 관리, 템플릿 관리, AI API 관리, 작성 결과/에디터
- 발행: 발행 설정, 발행 실행, 발행 채널 관리, 발행 이력
- 로그/모니터링: 실행 로그, 실패 로그, 재시도 큐

## DB 초기화
- 앱 실행 시 SQLite DB(`blogwriter_data/blogwriter.db`) 자동 생성
- 필요 시 마이그레이션 실행
  - `set PYTHONPATH=src`
  - `alembic upgrade head`
