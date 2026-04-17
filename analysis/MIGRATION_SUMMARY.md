# Analysis 폴더 이전 완료

## ✅ 완료된 작업

### 1. 폴더 구조 정리
- `/var/www/html/dj_voice_manage/analysis/` 폴더 생성
- 모든 분석 스크립트를 analysis 폴더로 이동
- 루트 디렉토리에서 분석 파일 제거

### 2. 경로 수정
모든 분석 스크립트의 Django 경로를 수정했습니다:

**이전:**
```python
sys.path.append('/var/www/html/dj_voice_manage')
```

**이후:**
```python
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
```

이제 스크립트가 어느 위치에서 실행되든 올바른 경로를 찾습니다.

### 3. 생성된 파일
```
/var/www/html/dj_voice_manage/analysis/
├── README.md                              (상세 가이드)
├── analyze_transcription_quality.py       (전사 품질 분석)
├── analyze_failed_records.py              (실패 레코드 분석)
├── analyze_files_per_identifier.py        (identifier별 파일 분석)
└── analyze_noise_level.py                 (소음 수준 분석)
```

## 🚀 사용 방법

### 기본 실행
```bash
cd /var/www/html/dj_voice_manage/analysis
python analyze_transcription_quality.py
python analyze_failed_records.py
python analyze_files_per_identifier.py
python analyze_noise_level.py
```

### 결과 저장
```bash
cd /var/www/html/dj_voice_manage/analysis
python analyze_transcription_quality.py > results_quality.txt
python analyze_failed_records.py > results_failed.txt
python analyze_files_per_identifier.py > results_identifiers.txt
python analyze_noise_level.py > results_noise.txt
```

### 일괄 실행
```bash
cd /var/www/html/dj_voice_manage/analysis
for script in analyze_*.py; do
    echo "Running $script..."
    python "$script" > "results_$(basename $script .py)_$(date +%Y%m%d).txt"
done
```

## ✅ 테스트 결과

모든 스크립트가 정상적으로 작동함을 확인했습니다:

### analyze_noise_level.py
```
✅ 소음 수준 통계 정상 출력
✅ 카테고리별 분포 정상 출력
✅ Identifier 포함 레코드 분석 정상
```

### analyze_files_per_identifier.py
```
✅ 아동 카테고리: 153명, 평균 33.62개/인
✅ 성인 카테고리: 248명, 평균 46.18개/인
✅ 파일 개수별 분포 정상 출력
```

### analyze_failed_records.py
```
✅ Failed 레코드: 407개 (2.37%)
✅ 카테고리별 Failed 분포 정상
✅ Identifier별 Failed 비율 분석 정상
```

## 📝 README.md 포함 내용

analysis/README.md 파일에는 다음 내용이 포함되어 있습니다:

1. **분석 스크립트 목록 및 역할**
   - 각 스크립트의 상세 설명
   - 사용법 및 출력 정보
   - 주요 메트릭 해석 가이드

2. **실행 방법**
   - 기본 실행
   - 출력 결과 저장
   - 일괄 실행 스크립트

3. **분석 결과 해석 가이드**
   - WER 점수 해석
   - 전사 완료율 기준
   - Identifier별 파일 수 기준

4. **기술 요구사항**
   - Python 환경
   - 데이터베이스 설정
   - 필요한 권한

5. **커스터마이징**
   - 카테고리 목록 수정 방법
   - 출력 형식 변경 방법
   - CSV 출력 추가 방법

6. **트러블슈팅**
   - 일반적인 오류 및 해결 방법
   - Django 설정 오류 해결
   - 메모리 부족 문제 해결

## 🎯 주요 개선사항

1. **경로 독립성**: 스크립트가 실행 위치에 관계없이 작동
2. **코드 가독성**: 명확한 주석과 구조화된 코드
3. **문서화**: 상세한 README.md로 사용 편의성 향상
4. **유지보수성**: 폴더 구조 개선으로 관리 용이

## 📂 폴더 구조 비교

### 이전
```
/var/www/html/dj_voice_manage/
├── analyze_transcription_quality.py
├── analyze_failed_records.py
├── analyze_files_per_identifier.py
├── analyze_noise_level.py
├── ... (기타 수십 개의 파일)
```

### 이후
```
/var/www/html/dj_voice_manage/
├── analysis/
│   ├── README.md
│   ├── analyze_transcription_quality.py
│   ├── analyze_failed_records.py
│   ├── analyze_files_per_identifier.py
│   └── analyze_noise_level.py
├── ... (기타 파일들)
```

## 🔄 향후 확장 가능성

새로운 분석 스크립트를 추가하려면:

1. `analysis/` 폴더에 새 Python 파일 생성
2. 다음 Django 설정 코드 포함:
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
3. 분석 로직 구현
4. README.md 업데이트

---

**작업 완료일:** 2026-01-31  
**작업자:** GitHub Copilot
