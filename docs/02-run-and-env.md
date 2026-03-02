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
- DB: `blogwriter_data/blogwriter.db`
- 웹셸 런타임: `blogwriter_data/web_shell_runtime`
- 웹에디터 런타임: `blogwriter_data/web_editor_runtime`
