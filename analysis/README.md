# 음성 데이터 분석 도구 (Analysis Tools)

이 폴더는 Django Voice Management 시스템에 저장된 음성 데이터를 분석하는 스크립트들을 포함합니다.

## 📋 분석 스크립트 목록

### 1. 전사 품질 분석 (`analyze_transcription_quality.py`)

**역할:**
- 자동 전사와 수동 교정의 품질을 종합 분석
- WER (Word Error Rate) 계산 및 통계 제공
- 전사 누락 현황 파악
- 카테고리별 전사 품질 비교

**사용법:**
```bash
cd /var/www/html/dj_voice_manage/analysis
python analyze_transcription_quality.py
```

**출력 정보:**
- 전사 현황 Overview (자동/수동 전사 비율)
- WER 분석 (평균, 중앙값, 분포)
- 전사 누락 현황 (Identifier 기준)
- 카테고리별 전사 현황
- 처리 시간 분석 (수동 교정 소요 시간)

**주요 메트릭:**
- WER (Word Error Rate): 자동 전사의 정확도 측정
- 전사 완료율: 자동/수동 전사 완료 비율
- 누락률: Identifier당 전사되지 않은 파일 비율

**사용 시나리오:**
- 전사 품질 모니터링이 필요할 때
- 연구 데이터의 품질 검증이 필요할 때
- 특정 카테고리의 전사 정확도 비교가 필요할 때

---

### 2. 실패 레코드 분석 (`analyze_failed_records.py`)

**역할:**
- 전사 실패(failed) 상태인 레코드들의 상세 분석
- 카테고리별/Identifier별 실패 패턴 파악
- 실패율이 높은 참가자 식별

**사용법:**
```bash
cd /var/www/html/dj_voice_manage/analysis
python analyze_failed_records.py
```

**출력 정보:**
- 전체 Failed 레코드 통계
- 카테고리별 Failed 분포
- Identifier별 Failed 건수 및 비율
- Failed 레코드 상세 정보 샘플
- Failed vs Unprocessed 비교
- 연구 기준(2,750개) 환산

**주요 메트릭:**
- Failed 비율: 전체 레코드 대비 실패 비율
- Identifier별 Failed 비율: 참가자별 실패율
- 100% Failed Identifier: 모든 파일이 실패한 참가자 수

**사용 시나리오:**
- 전사 실패 원인 파악이 필요할 때
- 특정 참가자의 데이터에 문제가 있을 때
- 데이터 품질 개선 전략 수립 시

---

### 3. Identifier별 파일 분석 (`analyze_files_per_identifier.py`)

**역할:**
- 참가자(Identifier)별 녹음 파일 개수 분석
- 카테고리별 참가자당 평균 파일 수 확인
- 데이터 수집 균형성 검증

**사용법:**
```bash
cd /var/www/html/dj_voice_manage/analysis
python analyze_files_per_identifier.py
```

**출력 정보:**
- 카테고리별 통계 (총 identifier 수, 총 파일 수)
- 평균/중앙값/최빈값 파일 수
- 파일 개수 분포 (상위 참가자)
- 파일 개수별 그룹 분포 (1-10개, 11-20개 등)

**주요 메트릭:**
- 평균 파일 수/인: 참가자당 평균 녹음 파일 수
- 중앙값: 파일 수의 중간값
- 최빈값: 가장 많은 참가자가 가진 파일 수

**사용 시나리오:**
- 데이터 수집 현황 파악이 필요할 때
- 참가자별 녹음 완료도 확인이 필요할 때
- 연구 목표(예: 1인당 50개 파일) 달성 여부 확인 시

---

### 4. 소음 수준 분석 (`analyze_noise_level.py`)

**역할:**
- 녹음 환경의 소음 수준(noise_level) 통계 분석
- 카테고리별 소음 분포 파악
- 데이터 품질 평가를 위한 환경 정보 제공

**사용법:**
```bash
cd /var/www/html/dj_voice_manage/analysis
python analyze_noise_level.py
```

**출력 정보:**
- 전체 소음 수준 기록 현황
- 소음 수준별 분포 (조용함, 보통, 시끄러움 등)
- 카테고리별 소음 수준 분포
- Identifier 포함 레코드의 소음 수준

**주요 메트릭:**
- 소음 수준 기록률: 소음 정보가 있는 레코드 비율
- 소음 수준별 분포: 각 소음 레벨의 파일 수
- 카테고리별 소음 패턴: 각 참가자 그룹의 녹음 환경

**사용 시나리오:**
- 녹음 환경 품질 확인이 필요할 때
- SNR 분석과 함께 데이터 품질 평가 시
- 소음이 많은 데이터 필터링이 필요할 때

---

## 🚀 실행 방법

### 기본 실행
```bash
# analysis 폴더로 이동
cd /var/www/html/dj_voice_manage/analysis

# 원하는 스크립트 실행
python analyze_transcription_quality.py
python analyze_failed_records.py
python analyze_files_per_identifier.py
python analyze_noise_level.py
```

### 출력 결과 저장
```bash
# 터미널 출력을 파일로 저장
python analyze_transcription_quality.py > results_quality.txt
python analyze_failed_records.py > results_failed.txt
python analyze_files_per_identifier.py > results_identifiers.txt
python analyze_noise_level.py > results_noise.txt
```

### 일괄 실행
```bash
# 모든 분석 스크립트 실행 및 결과 저장
cd /var/www/html/dj_voice_manage/analysis
for script in analyze_*.py; do
    echo "Running $script..."
    python "$script" > "results_$(basename $script .py).txt"
done
```

---

## 📊 분석 결과 해석 가이드

### WER (Word Error Rate)
- **0-5%**: 매우 우수한 전사 품질
- **5-10%**: 우수한 품질
- **10-20%**: 양호한 품질
- **20-30%**: 보통 품질 (수동 교정 필요)
- **30%+**: 낮은 품질 (대폭 교정 필요)

### 전사 완료율
- **90% 이상**: 목표 달성
- **80-90%**: 양호 (추가 작업 필요)
- **80% 미만**: 미달 (집중 작업 필요)

### Identifier별 파일 수
- 연구 목표에 따라 다름 (예: 아동 50개, 성인 30개 등)
- 표준편차가 클 경우 데이터 수집 불균형 의미

---

## ⚙️ 기술 요구사항

### Python 환경
- Python 3.8 이상
- Django 프로젝트 환경 설정 필요

### 데이터베이스
- SQLite 또는 PostgreSQL
- Django ORM을 통한 접근

### 필요한 권한
- 데이터베이스 읽기 권한
- Django 프로젝트 settings 접근 권한

---

## 🔧 커스터마이징

### 분석 기준 변경
각 스크립트의 상단에서 다음 항목들을 수정할 수 있습니다:

```python
# 카테고리 목록
categories = {
    'child': '아동',
    'senior': '성인',
    'atypical': '음성 장애',
    'auditory': '청각 장애',
    'normal': '일반'
}

# 연구 기준 레코드 수
TARGET_RECORDS = 2750
```

### 출력 형식 변경
- 프린트 문 수정으로 출력 형식 변경 가능
- CSV 출력이 필요한 경우 pandas 추가 후 DataFrame 변환

---

## 🐛 트러블슈팅

### Django 설정 오류
```
ModuleNotFoundError: No module named 'voice_project'
```
**해결:** Django 프로젝트 경로가 올바른지 확인

### 데이터베이스 연결 오류
```
django.db.utils.OperationalError: no such table
```
**해결:** 마이그레이션 실행 확인
```bash
cd /var/www/html/dj_voice_manage
python manage.py migrate
```

### 메모리 부족
대용량 데이터 분석 시 메모리 부족 발생 가능
**해결:** 쿼리셋을 iterator()로 변경하거나 배치 처리

---

## 📝 추가 개발 가이드

### 새로운 분석 스크립트 추가
1. `analysis/` 폴더에 새 Python 파일 생성
2. Django 설정 코드 포함:
```python
import os
import sys
import django

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_project.settings')
django.setup()

from voice_app.models import AudioRecord
```
3. 분석 함수 구현
4. `if __name__ == '__main__':` 블록에서 함수 호출

### 분석 결과 시각화
- matplotlib 또는 seaborn 사용
- 그래프를 PNG 파일로 저장

---

## 📞 지원 및 문의

분석 스크립트 관련 문제나 새로운 분석 요구사항이 있으면 개발팀에 문의하세요.

**마지막 업데이트:** 2026-01-31
