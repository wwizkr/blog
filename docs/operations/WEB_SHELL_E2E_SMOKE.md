# Web Shell E2E Smoke

웹셸 주요 플로우(수집 -> 라벨 -> 작성 -> 발행 -> 모니터링) API 연결 상태를 빠르게 점검하는 스크립트입니다.

## 실행

```bash
py -3 scripts/webshell_e2e_smoke.py --base-url http://127.0.0.1:8000
```

## 저장 API까지 검증

아래 옵션은 현재 설정값을 다시 저장(POST)하며, 값 변경은 하지 않습니다.

```bash
py -3 scripts/webshell_e2e_smoke.py --base-url http://127.0.0.1:8000 --verify-save
```

## 출력

- 단계별 `OK` / `FAIL`
- 실패 시 `error_code`, `request_id` 포함
- 마지막 요약(`total`, `fail`)
