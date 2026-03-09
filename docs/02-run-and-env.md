# 02. 실행/환경 설정

## 실행
```powershell
set PYTHONPATH=src
python run.py
```

## 의존성 설치
```powershell
pip install -r requirements.txt
```

## 마이그레이션
```powershell
set PYTHONPATH=src
alembic upgrade head
```

## 데이터 경로
- 기본 DB: `mublo_ops_data/mublo_ops.db`
- 기본 웹셸 런타임: `mublo_ops_data/web_shell_runtime`
- 기본 웹에디터 런타임: `mublo_ops_data/web_editor_runtime`

## 메모
- 제품명 전환에 맞춰 신규 기본 저장 경로는 `mublo_ops_data`를 사용
