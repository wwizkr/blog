# 콘텐츠 자동화 시스템 전체 운영 설계 문서
Version: 1.0  
목적: 수집 → 라벨링 → 작성 → 발행을 독립 모듈로 설계하고
각 설정에 따라 주기적으로 실행되는 자동화 구조 정의

---

# 1. 시스템 철학

본 시스템은 하나의 거대한 파이프라인이 아니라,

- 수집 (Crawl)
- 라벨링 (Labeling)
- 작성 (Writing)
- 발행 (Publishing)

을 **완전히 독립된 모듈**로 설계한다.

각 모듈은:

- 독립 실행 가능
- 독립 스케줄링 가능
- 독립 설정 관리
- 실패해도 다른 모듈에 영향 없음

---

# 2. 전체 아키텍처 구조

Crawl Service
    ↓ (DB 저장)
Labeling Service
    ↓ (라벨 저장)
Writer Service
    ↓ (초안 저장)
Publisher Service
    ↓ (채널 발행)

각 단계는 DB를 통해 연결되며
직접 호출 구조가 아니라 상태 기반 흐름을 사용한다.

---

# 3. 모듈별 역할 정의

---

# 3.1 수집 (Crawl Module)

## 역할

- 외부 콘텐츠 수집
- 텍스트/이미지 DB 저장
- keyword 기반 저장
- 중복 제거

## 실행 방식

- 스케줄 기반 (예: 10분, 30분, 1시간)
- 키워드 설정별 실행 가능

## 상태값

content:
- crawl_status = completed
- label_status = pending

---

# 3.2 라벨링 (Labeling Module)

## 역할

- 수집된 데이터 분석
- Rule 기반 1차 분류
- Confidence 계산
- API 쿼터 고려한 단계적 분석
- content_labels / image_labels 저장

## 실행 방식

- 일정 주기 실행
- pending 상태만 처리
- API 일일 쿼터 확인

## 상태값

- label_status = completed
- confidence 저장

---

# 3.3 작성 (Writer Module)

## 역할

- 라벨링 완료된 콘텐츠 활용
- Persona + Template 기반 초안 생성
- Source 요약 삽입
- Channel 맞춤 포맷 적용
- draft 상태로 저장

## 실행 조건

- label_status = completed
- writing_enabled = true
- 설정된 생성 주기 도달

## 상태값

article:
- status = draft
- publish_status = pending

---

# 3.4 발행 (Publisher Module)

## 역할

- 초안 콘텐츠 채널별 발행
- 채널 API 호출
- 발행 결과 저장
- 실패 시 재시도

## 실행 조건

- publish_enabled = true
- 예약 시간 도달
- status = draft

## 상태값

- publish_status = published
- publish_error_count 증가

---

# 4. 실행 방식 설계

각 모듈은 다음 방식 중 하나로 실행 가능:

1. 내부 스케줄러 (Python scheduler)
2. OS cron
3. 외부 Task Runner
4. 수동 실행 버튼

권장 방식:

- exe 환경 → 내부 스케줄러
- 서버 환경 → cron

---

# 5. 설정 구조

각 모듈은 독립 설정을 가진다.

## Crawl Settings

- 활성화 여부
- 실행 주기
- 키워드 리스트
- source_limit

## Labeling Settings

- 활성화 여부
- 실행 주기
- free_api_daily_limit
- paid_api_daily_limit
- confidence_threshold

## Writing Settings

- 활성화 여부
- 실행 주기
- persona_id
- template_id
- source_limit

## Publishing Settings

- 활성화 여부
- 실행 주기
- 채널별 API 설정
- 발행 예약 여부

---

# 6. 상태 기반 흐름 (중요)

모듈 간 직접 호출을 하지 않는다.

상태 기반 처리 흐름:

1. 수집 → crawl_status = completed
2. 라벨링 → label_status = completed
3. 작성 → article.status = draft
4. 발행 → publish_status = published

이 구조의 장점:

- 장애 격리
- 재시도 가능
- 단계별 테스트 가능
- 병렬 처리 가능

---

# 7. 스케줄링 전략

예시 구성:

- Crawl: 30분마다
- Labeling: 15분마다
- Writing: 1시간마다
- Publishing: 10분마다

또는 설정값 기반 동적 조정 가능.

---

# 8. 쿼터 관리 전략

Labeling 및 Writing 단계에서:

- API 호출 카운트 기록
- 일일 리셋 시간 설정
- 초과 시 다음 실행 주기로 이월

---

# 9. 장애 대응 전략

각 모듈은 다음 원칙을 따른다:

- 예외 발생 시 로그 기록
- 다음 대상 처리 계속 진행
- 실패 카운트 증가
- 특정 횟수 초과 시 상태 전환

---

# 10. 확장 전략

이 구조는 다음 확장이 가능하다:

- 다중 키워드 그룹 운영
- 다중 페르소나 자동 로테이션
- 채널별 발행 전략 분리
- 성과 기반 자동 템플릿 선택
- A/B 생성 실험

---

# 11. 핵심 설계 원칙

1. 모든 단계는 독립적이어야 한다.
2. DB 상태가 흐름을 제어한다.
3. API 쿼터는 중앙 관리한다.
4. 각 단계는 반복 실행 가능해야 한다.
5. 실패해도 시스템은 멈추지 않는다.

---

# 결론

현재 계획의 핵심은:

수집, 라벨링, 작성, 발행을 독립적으로 설계하고  
각 설정에 따라 주기적으로 실행하는 구조를 유지하는 것이다.

이 구조는:

- exe 배포 환경에 적합
- 확장 가능
- 비용 통제 가능
- 장애에 강함
- 장기 운영에 적합

이는 단순 자동화가 아니라  
콘텐츠 자동 생산 파이프라인의 운영 아키텍처이다.