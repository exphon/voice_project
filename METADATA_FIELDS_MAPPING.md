# 메타데이터 필드 매핑 문서

## 업데이트 일자
2025-10-11

## 개요
React Native 앱에서 Django 백엔드로 전송되는 모든 메타데이터 필드와 저장 위치를 정리한 문서입니다.

---

## 1. 공통 필드 (AudioRecord 모델 직접 필드)

### 1.1 기본 식별 정보
| 앱 필드명 | Django 모델 필드 | 타입 | 카테고리 |
|----------|-----------------|------|---------|
| identifier | identifier | CharField(6) | 전체 |
| name | name | CharField(100) | 전체 |

### 1.2 인구통계학적 정보
| 앱 필드명 | Django 모델 필드 | 타입 | 카테고리 |
|----------|-----------------|------|---------|
| gender | gender | CharField(10) | 전체 |
| age | age | CharField(3) | 전체 |
| birthDate | birth_year, birth_month, birth_day | CharField | 전체 |
| birthYear | birth_year | CharField(4) | 전체 |
| birthMonth | birth_month | CharField(2) | 전체 |
| birthDay | birth_day | CharField(2) | 전체 |

### 1.3 녹음 환경 정보
| 앱 필드명 | Django 모델 필드 | 타입 | 카테고리 |
|----------|-----------------|------|---------|
| place / recordingLocation | recording_location | CharField(50) | 전체 |
| noise / noiseLevel | noise_level | CharField(20) | 전체 |
| device / deviceType | device_type | CharField(30) | 전체 |
| mic / hasMicrophone | has_microphone | CharField(10) | 전체 |
| diagnosis | diagnosis | CharField(50) | 전체 |

### 1.4 SNR 정보
| 앱 필드명 | Django 모델 필드 | 타입 | 카테고리 |
|----------|-----------------|------|---------|
| snr_mean | snr_mean | FloatField | 전체 |
| snr_max | snr_max | FloatField | 전체 |
| snr_min | snr_min | FloatField | 전체 |

---

## 2. 카테고리별 특화 필드 (category_specific_data JSON)

### 2.1 Child 전용 필드
| 앱 필드명 | category_specific_data 키 | 타입 | 설명 |
|----------|--------------------------|------|------|
| ageInMonths | age_in_months | String | 개월 수 |
| subjective_rating | subjective_rating | String | 주관적 평가 |
| pronunProblem | pronunciation_problem | String | 발음 문제 유무 |

### 2.2 Senior 전용 필드
| 앱 필드명 | category_specific_data 키 | 타입 | 설명 |
|----------|--------------------------|------|------|
| education | education | String | 학교 선택 |
| educationYears | education_years | String | 교육 년수 |
| finalEducation / educationLevel | final_education | String | 총 교육년수 |
| educationDetail | education_detail | String | 교육 상세 |
| cognitiveDecline | cognitive_decline | String | 인지 저하 |
| subjectiveScore | subjective_score | String | 주관적 평가 점수 |
| subjectiveNote | subjective_note | String | 주관적 평가 메모 |
| job | job | String | 직업 |

### 2.3 Auditory 전용 필드

#### 교육 정보
| 앱 필드명 | category_specific_data 키 | 타입 | 설명 |
|----------|--------------------------|------|------|
| education | education | String | 교육 수준 |
| educationDetail | education_detail | String | 교육 상세 |
| finalEducation | final_education | String | 총 교육년수 |

#### 청각 관련
| 앱 필드명 | category_specific_data 키 | 타입 | 설명 |
|----------|--------------------------|------|------|
| hearingLevel / hearingDegree | hearing_level | String | 청력 수준 |
| hearingLossDuration | hearing_loss_duration | String | 난청 기간 |
| hasHearingAid | has_hearing_aid | String | 보청기 착용 여부 |
| hearingAidDuration | hearing_aid_duration | String | 보청기 착용 기간 |
| hearingOnsetType | hearing_onset_type | String | 청각 발병 유형 |
| hearingImpairment | hearing_impairment | String | 청각 장애 정보 |

#### 인지 관련
| 앱 필드명 | category_specific_data 키 | 타입 | 설명 |
|----------|--------------------------|------|------|
| cognitiveLevel / cognitiveImpairment | cognitive_level | String | 인지 수준 |

#### 언어 관련
| 앱 필드명 | category_specific_data 키 | 타입 | 설명 |
|----------|--------------------------|------|------|
| nativeLanguage | native_language | String | 모국어 |
| languageExperience | language_experience | String | 언어 경험 |

#### 배경소음 측정
| 앱 필드명 | category_specific_data 키 | 타입 | 설명 |
|----------|--------------------------|------|------|
| session_id | session_id | String | 세션 ID |
| background_noise_average | background_noise_average | String | 평균 배경소음 |
| background_noise_max | background_noise_max | String | 최대 배경소음 |
| background_noise_min | background_noise_min | String | 최소 배경소음 |
| noise_measurement_time | noise_measurement_time | String | 소음 측정 시간 |
| platform | platform | String | iOS/Android |
| ageInMonths | age_in_months | String | 개월 수 |

### 2.4 공통 작업 정보 (모든 카테고리)
| 앱 필드명 | category_specific_data 키 | 타입 | 설명 |
|----------|--------------------------|------|------|
| region | region | String | 거주 지역 |
| task_type | task_type | String | 작업 유형 |
| sentence_index | sentence_index | String | 문장 인덱스 |
| sentence_text | sentence_text | String | 문장 텍스트 |
| upload_timestamp | upload_timestamp | String | 업로드 시각 |
| local_saved | local_saved | String | 로컬 저장 여부 |
| recordingDate | recording_date | String | 녹음일자 |
| retry_count | retry_count | String | 재시도 횟수 |
| attempt | attempt | String | 시도 횟수 |
| question_file | question_file | String | 질문 파일명 |
| current_page | current_page | String | 현재 페이지 |
| page_name | page_name | String | 페이지 이름 |

### 2.5 메타데이터 JSON
| 앱 필드명 | category_specific_data 키 | 타입 | 설명 |
|----------|--------------------------|------|------|
| metadata_json | metadata_json | String (JSON) | 전체 메타데이터 JSON |
| metadata_filename | metadata_filename | String | 메타데이터 파일명 |

---

## 3. 업로드 엔드포인트

| 카테고리 | URL | 비고 |
|---------|-----|------|
| Child | /api/child/upload/ | C12345 형식 identifier |
| Senior | /api/senior/upload/ | S12345 형식 identifier |
| Auditory | /api/auditory/upload/ | A12345 형식 identifier |

---

## 4. Django 모델 구조

```python
class AudioRecord(models.Model):
    # 공통 필드 (1.1~1.4)
    identifier = models.CharField(max_length=6, ...)
    name = models.CharField(max_length=100, ...)
    gender = models.CharField(max_length=10, ...)
    # ... (상세는 models.py 참조)
    
    # 카테고리별 특화 JSON
    category_specific_data = models.JSONField(default=dict, blank=True)
```

---

## 5. 확인 방법

### Django shell에서 확인
```python
python manage.py shell

from voice_app.models import AudioRecord
ar = AudioRecord.objects.get(id=1425)

# 공통 필드
print(ar.identifier, ar.name, ar.gender, ar.age)

# 카테고리별 특화 데이터
print(ar.category_specific_data)
print(ar.get_category_data('region'))
print(ar.get_category_data('hearing_level'))  # auditory만
```

### 로그에서 확인
업로드 시 다음 로그 확인:
```
[DEBUG] Identifier from request: C12345
[DEBUG] Category: child, Identifier: C12345
[DEBUG] Category specific data keys: ['region', 'task_type', ...]
[DEBUG] Category specific data count: 8
```

---

## 6. 주의사항

1. **identifier 형식**: 반드시 대문자 C/S/A + 5자리 숫자
2. **birthDate 파싱**: YYYY-MM-DD 형식을 year/month/day로 자동 분리
3. **메타데이터 JSON**: Base64 인코딩 또는 직접 JSON 문자열 모두 지원
4. **카테고리별 필드**: 해당 카테고리가 아니면 저장 안 됨 (예: child에 hearing_level 전송해도 무시)
5. **필드 별칭**: place=recordingLocation, noise=noiseLevel 등 양쪽 모두 허용

---

## 7. 업데이트 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2025-10-11 | identifier 저장 로직 추가, Auditory 전용 필드 완전 지원 추가 |
| 2025-10-11 | 작업 특화 정보 필드 추가 (retry_count, attempt, question_file 등) |
