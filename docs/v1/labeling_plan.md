# 콘텐츠 텍스트 및 이미지 라벨링 시스템 설계 문서
Version: 1.0  
목적: 자동 콘텐츠 생성 엔진을 위한 구조적 메타데이터 생성

---

# 1. 시스템 개요

본 시스템은 다음과 같은 구조로 동작한다.

1. 수집 모듈은 별도로 실행된다.
2. 텍스트 및 이미지 데이터를 DB에 저장한다.
3. 라벨링 모듈은 정해진 시간마다 반복 실행된다.
4. API 쿼터(무료/유료)를 고려하여 단계적으로 라벨을 확정한다.

라벨은 단순 분류 목적이 아니라  
자동 콘텐츠 생성 엔진의 학습 및 프롬프트 구성 데이터로 활용된다.

---

# 2. 전체 아키텍처

Crawl Service (별도 실행)
        ↓
Database 저장 (content, images)
        ↓
Labeling Scheduler (주기 실행)
        ↓
Rule Engine (1차 분석)
        ↓
Confidence 계산
        ↓
Free API (선별 호출)
        ↓
Paid API (극소수 호출)
        ↓
content_labels / image_labels 저장

---

# 3. 실행 흐름

## 3.1 수집 단계 (별도 프로세스)

- 블로그/웹 콘텐츠 수집
- 이미지 URL 및 메타데이터 저장
- DB 저장 시 상태값:
    - label_status = 'pending'

수집과 라벨링은 완전히 분리한다.

---

## 3.2 라벨링 스케줄러

라벨링은 주기적으로 실행된다.

예:
- 10분마다 실행
- 또는 매 시간 실행
- 또는 하루 N회 실행

실행 시:

1. label_status = 'pending'
2. 최근 N건 (쿼터 고려)
3. 미라벨링 데이터만 조회

---

# 4. 쿼터 기반 실행 전략

## 4.1 일일 쿼터 설정

config 예시:

- free_api_daily_limit = 200
- paid_api_daily_limit = 20
- rule_only_unlimited = true

## 4.2 라벨링 처리 전략

1. Rule 기반 분석은 무제한 수행
2. confidence ≥ threshold_high → 즉시 확정
3. threshold_mid ≤ confidence < threshold_high → Free API 호출
4. confidence < threshold_mid → Paid API 후보로 큐 적재
5. Paid API는 일일 쿼터 내에서만 실행

---

# 5. 텍스트 라벨 체계

## 5.1 기본 분류

- topics
- tone
- sentiment
- quality_score

## 5.2 구조 라벨 (자동 생성 핵심)

- structure_type
- title_type
- paragraph_pattern
- cta_present

## 5.3 SEO 라벨

- main_keyword
- sub_keywords
- keyword_density
- faq_structure
- h_tag_pattern

## 5.4 감정 / 상업성

- emotion_level (1~5)
- stimulation_level
- commercial_intent

## 5.5 신뢰도

- confidence (0~1 float)

---

# 6. 이미지 라벨 체계

## 6.1 기본

- category (음식, 숙소, 풍경, 인물, 제품 등)
- mood (밝음, 어두움 등)
- contains_person (boolean)
- text_overlay (boolean)
- thumbnail_score (float)

## 6.2 확장 가능 항목

- hero_image_candidate
- composition_type
- color_temperature

---

# 7. Confidence 계산 로직

Confidence는 다음 요소를 기반으로 계산한다.

- 키워드 매칭 개수
- 구조 패턴 명확성
- 감정 단어 빈도
- 제목 유형 인식 여부
- 텍스트 길이
- 라벨 간 일관성

예시:

confidence =
    (keyword_score * 0.3) +
    (structure_score * 0.3) +
    (emotion_score * 0.2) +
    (title_pattern_score * 0.2)

---

# 8. 라벨 상태 관리

content 테이블에 다음 컬럼 추가:

- label_status
    - pending
    - rule_done
    - free_api_done
    - paid_api_done
    - completed

- label_attempt_count
- last_labeled_at

---

# 9. 스케줄 실행 알고리즘

1. 오늘의 API 사용량 확인
2. pending 데이터 조회 (limit 적용)
3. Rule 분석 실행
4. confidence 계산
5. Free API 호출 가능 여부 판단
6. Paid API 호출 가능 여부 판단
7. 결과 저장
8. label_status 업데이트

---

# 10. DB 스키마 예시

## content_labels

- id
- content_id
- topics (json)
- tone
- structure_type
- emotion_level
- commercial_intent
- seo_score
- confidence
- created_at

## image_labels

- id
- image_id
- category
- mood
- contains_person
- thumbnail_score
- confidence
- created_at

---

# 11. 장애 대비 전략

- API 실패 시 retry_count 증가
- 3회 이상 실패 시 다음 스케줄로 이월
- API 응답 파싱 실패 시 로그 저장
- 라벨 불완전 시 rule_only 저장

---

# 12. 운영 전략

- 초기 단계: Rule 비중 높음
- 데이터 누적 후: Free API 활용 증가
- 고성과 콘텐츠 분석 시: Paid API 선별 사용

---

# 13. 목표

이 시스템은 단순 라벨러가 아니라:

1. 콘텐츠 자동 생성 프롬프트 구성 데이터 제공
2. 고성과 구조 패턴 축적
3. SEO 및 상업성 분석 데이터 축적
4. 비용 통제 가능한 하이브리드 LLM 활용 구조

---

# 14. 향후 확장

- 성과 데이터 연동 (조회수, 체류시간)
- 클러스터 기반 대표 문서 분석
- 자동 생성 엔진과 직접 연결
- 라벨 기반 A/B 생성 실험

---

# 결론

- 수집과 라벨링은 분리한다.
- 라벨링은 스케줄 기반 반복 실행한다.
- API 쿼터를 고려한 단계적 호출 구조를 유지한다.
- Rule → Free → Paid 순으로 확정한다.
- 모든 것은 confidence 기반으로 움직인다.

이 설계는 exe 배포 환경에서도 안정적으로 동작 가능하다.