# 발행 자동 반복 전환 계획

## 목표
- `발행 채널 관리` 서브메뉴를 제거한다.
- `발행 설정` 화면에서 채널별 발행 정책을 설정한다.
- 채널별 주기/모드에 따라 자동 반복 발행이 동작하도록 구현한다.

## 범위
- 메뉴 구조
  - `publish.channels` 제거
  - `publish.settings`, `publish.run`, `publish.history` 유지
- 발행 설정
  - 채널별 정책 테이블/편집 UI 제공
  - 항목: `발행 주기(분)`, `모드(auto/semi_auto)`, `발행형식`, `작성형식`, `API URL`
- 자동 반복 엔진
  - `auto` 채널만 주기적으로 처리
  - 처리 대상: `ready` 상태 글
  - 처리 방식: 발행 Job 생성 후 즉시 처리
- 발행 실행
  - 자동 반복 상태 확인
  - 시작/중지
  - 최근 자동 발행 로그 확인

## 데이터/정책
- 기존 `publish_channel_settings` 사용 (채널별 주기/모드 저장)
- `publish_mode = auto` 인 채널만 자동 반복 대상
- 같은 채널에서 이미 발행 완료된 글은 자동 반복 대상 제외

## API 변경
- 유지
  - `GET /api/publish-channel-settings`
  - `POST /api/publish-channel-settings/save`
- 추가
  - `GET /api/publish/auto/status`
  - `POST /api/publish/auto/start`
  - `POST /api/publish/auto/stop`
  - `POST /api/publish/auto/tick` (수동 1회 실행)

## UI 변경
- `발행 설정`
  - 글로벌 옵션 + 채널별 설정 편집 패널 통합
- `발행 실행`
  - 자동 반복 상태 카드
  - 시작/중지/즉시 1회 실행 버튼
  - 자동 발행 로그 테이블
- `발행 채널 관리`
  - 메뉴 제거(라우팅 제거)

## 구현 순서
1. 메뉴/라우팅에서 `publish.channels` 제거
2. 발행 설정 화면에 채널별 설정 편집 통합
3. 자동 반복 엔진(백그라운드 워커) 추가
4. 발행 실행 화면에 자동 반복 제어/로그 연결
5. 검증(컴파일/런타임 체크)
