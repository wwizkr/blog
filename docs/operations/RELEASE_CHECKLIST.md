# 릴리즈 체크리스트

## 마이그레이션/데이터
- [ ] DB 스키마 변경 여부 확인
- [ ] 신규 설정 키 기본값 검증
- [ ] 하위호환 불가 변경 공지 반영
- [ ] 저장 경로가 `mublo_ops_data` 기준으로 연결되는지 확인

## 웹셸 자산
- [ ] `src/ui/assets/web-shell/*` 변경 반영
- [ ] 활성 데이터 경로의 `web_shell_runtime/assets/web-shell/*` 동기화
- [ ] 메뉴 진입/핵심 플로우 수동 점검
- [ ] 제품명/표시명이 `MubloOps` 기준으로 반영되었는지 점검

## 품질
- [ ] `node --check src/ui/assets/web-shell/app.js`
- [ ] `py -3 -m py_compile src/ui/web_shell.py`
- [ ] 주요 API smoke test (`collect/label/writer/publish/monitor`)

## 운영
- [ ] 민감정보 정책 준수 확인 (`docs/operations/SENSITIVE_DATA_POLICY.md`)
- [ ] 장애 대응/롤백 포인트 기록
