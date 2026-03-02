# 03. 소스 구조

```text
src/
├─ app.py
├─ collector/
├─ core/
│  ├─ menu.py
│  ├─ settings.py
│  ├─ settings_keys.py
│  ├─ contracts.py
│  └─ related_keyword_service.py
├─ labeling/
├─ publisher/
├─ storage/
├─ ui/
└─ writer/
```

## 구조 원칙
1. 도메인별 디렉토리 분리
2. 공통 정책/키/계약은 `core`에 배치
3. UI는 `ui`, 영속성은 `storage` 집중
4. 실험/임시 데이터는 루트 `tmp/`만 사용
