# 🎙️ 특수화자 음성 데이터 통합 관리 시스템 - 발명 특허 기술 문서

## 📋 발명의 명칭
**"다중 화자 카테고리 기반의 음성 데이터 수집, 분석 및 품질 관리 통합 시스템"**

---

## 🎯 발명의 개요

본 발명은 특수화자(아동, 장노년, 청각장애인 등)의 음성 데이터를 체계적으로 수집, 관리, 분석하기 위한 모바일-웹 통합 플랫폼으로, AI 기반 자동 전사, 실시간 품질 분석, 메타데이터 자동 추출 및 관리 기능을 제공하는 시스템입니다.

---

## 🔬 발명의 배경 및 해결하고자 하는 과제

### 1. 기술적 배경

기존 음성 데이터 수집 시스템의 문제점:
- **비표준화된 메타데이터**: 화자 정보가 일관성 없이 수집됨
- **품질 관리 부재**: 수집 후 음성 품질을 확인할 수 없음
- **카테고리별 특화 정보 손실**: 아동/성인/청각장애인 등 각 그룹의 특수 정보가 체계적으로 관리되지 않음
- **수작업 전사 의존**: 음성을 텍스트로 변환하는 과정이 비효율적
- **데이터 무결성 문제**: 파일 손상, 메타데이터 손실 등 품질 저하

### 2. 해결하고자 하는 과제

✅ **과제 1**: 모바일 앱에서 수집한 음성 데이터의 실시간 품질 검증  
✅ **과제 2**: 화자 카테고리별 맞춤형 메타데이터 자동 관리  
✅ **과제 3**: AI 기반 자동 전사 및 수동 보정 이중 시스템 구현  
✅ **과제 4**: SNR 기반 음성 품질 자동 측정 및 시각화  
✅ **과제 5**: 손상된 오디오 파일의 자동 복구 및 형식 변환  
✅ **과제 6**: 동일 화자의 다중 녹음 데이터 통합 관리 (Identifier 시스템)  

---

## 💡 발명의 핵심 기술 구성

### 1. **적응형 카테고리 기반 메타데이터 관리 시스템**

#### 1.1 기술적 특징
```python
# 특허 청구항 핵심 코드
class AudioRecord(models.Model):
    # 공통 필드 (모든 화자 카테고리)
    identifier = models.CharField(max_length=6, validators=[identifier_validator])
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    
    # 카테고리별 특화 데이터를 저장하는 JSON 필드
    category_specific_data = models.JSONField(default=dict, blank=True)
    
    # 성능 최적화를 위한 인덱스 필드
    education_level = models.IntegerField(db_index=True)  # Senior/Auditory
    hearing_level = models.CharField(db_index=True)       # Auditory
    age_in_months = models.IntegerField()                 # Child/Auditory
```

#### 1.2 혁신성
- **5가지 화자 카테고리 지원**: 아동(Child), 성인(Senior), 음성장애(Atypical), 청각장애(Auditory), 일반(Normal)
- **JSON 기반 확장 가능한 스키마**: 카테고리별로 다른 메타데이터 구조를 동적으로 관리
- **성능 최적화 인덱싱**: 자주 쿼리되는 필드는 별도 컬럼으로 추출하여 검색 속도 향상
- **Identifier 기반 화자 추적**: C/S/A + 5자리 숫자로 동일 화자의 모든 녹음 추적

#### 1.3 카테고리별 특화 필드

**아동(Child)**:
- 월령(age_in_months), 발음 문제 유무, 주관적 평가, 녹음 장소

**성인(Senior)**:
- 교육년수, 인지 저하 여부, 직업, 음성 문제 유무

**청각장애(Auditory)**:
- 청력 수준(6단계), 청력 손실 기간, 보청기 사용 여부 및 기간, 인지 수준, 모국어/언어 경험

---

### 2. **AI 기반 이중 전사 시스템**

#### 2.1 기술 구조
```
┌─────────────────────────────────────────────────────┐
│  Whisper AI 자동 전사 (불변)                         │
│  ↓ transcript 필드 (읽기 전용)                       │
├─────────────────────────────────────────────────────┤
│  수동 보정 전사 (편집 가능)                          │
│  ↓ manual_transcript 필드 (사용자 수정)              │
└─────────────────────────────────────────────────────┘
```

#### 2.2 핵심 알고리즘
```python
# Whisper 모델 싱글톤 로딩 (메모리 최적화)
model = whisper.load_model("base")  # 전역 로딩

def transcribe_audio(audio_path):
    """음성 파일을 한국어로 자동 전사"""
    result = model.transcribe(
        audio_path, 
        fp16=False,           # CPU 호환성
        temperature=0.0,      # 일관성 향상
        language="ko"         # 한국어 고정
    )
    return result['text']

# WhisperX Forced Alignment (단어/음소 수준 타임스탬프)
def transcribe_and_align_whisperx(audio_path):
    """단어 단위 시간 정렬 수행"""
    # 1단계: ASR
    result = whisperx_model.transcribe(audio_path)
    
    # 2단계: Alignment
    aligned_result = whisperx.align(
        result["segments"], 
        alignment_model, 
        metadata, 
        audio_path
    )
    return aligned_result
```

#### 2.3 혁신성
✅ **원본 보존**: AI 전사 결과는 수정 불가로 보존, 연구 재현성 확보  
✅ **수동 보정 분리**: 사용자 수정 사항은 별도 필드에 저장  
✅ **WhisperX 통합**: 단어 단위 타임스탬프로 정밀한 음성-텍스트 정렬  
✅ **Lazy Loading**: 모델을 전역에서 한 번만 로드하여 메모리 절약  

---

### 3. **실시간 음성 품질 분석 시스템 (SNR 기반)**

#### 3.1 SNR 측정 기술
```python
# 데이터 모델
snr_mean = models.FloatField(help_text='평균 SNR 값')
snr_max = models.FloatField(help_text='최대 SNR 값')
snr_min = models.FloatField(help_text='최소 SNR 값')

# 모바일 앱에서 실시간 측정 후 서버로 전송
POST /api/upload/ {
    "audio_file": <file>,
    "snr_mean": 15.3,
    "snr_max": 22.1,
    "snr_min": 8.7,
    ...
}
```

#### 3.2 품질 기준 자동 분류
| SNR 범위 | 품질 등급 | 활용 가능성 |
|---------|---------|------------|
| > 20 dB | 우수 | 모든 연구에 적합 |
| 15-20 dB | 양호 | 대부분의 분석 가능 |
| 10-15 dB | 보통 | 제한적 사용 |
| < 10 dB | 불량 | 재녹음 권장 |

#### 3.3 시각화 기술
```javascript
// WaveSurfer.js 기반 대칭 dB 스케일 파형 표시
wavesurfer = WaveSurfer.create({
    container: '#waveform',
    waveColor: '#007bff',
    progressColor: '#28a745',
    height: 120,
    barWidth: 2,
    barGap: 2,
    normalize: true,  // 대칭 정규화
    backend: 'WebAudio'
});
```

#### 3.4 혁신성
✅ **3가지 SNR 지표**: 평균/최대/최소값으로 음질 종합 평가  
✅ **실시간 측정**: 녹음 직후 모바일 앱에서 SNR 계산  
✅ **자동 품질 분류**: 임계값 기반 품질 등급 자동 부여  
✅ **파형 시각화**: dB 스케일 정규화로 음성 특성 직관적 표시  

---

### 4. **손상 오디오 파일 자동 복구 시스템**

#### 4.1 문제 상황
모바일 녹음 중 앱 강제 종료나 비정상 중단 시 발생:
```
Error: moov atom not found
→ MP4/M4A 메타데이터(moov atom) 누락으로 파일 재생 불가
```

#### 4.2 복구 알고리즘
```python
def convert_m4a_to_wav(input_path, output_path):
    """손상된 오디오 파일 복구 및 WAV 변환"""
    
    # 1차 시도: 일반 변환
    command = ['ffmpeg', '-y', '-i', input_path, 
               '-acodec', 'pcm_s16le', '-ar', '16000', 
               '-ac', '1', output_path]
    result = subprocess.run(command)
    
    # 2차 시도: moov atom 누락 감지 시 복구 모드
    if "moov atom not found" in result.stderr:
        recovery_command = [
            'ffmpeg', '-y', 
            '-err_detect', 'ignore_err',  # 오류 무시
            '-i', input_path,
            '-acodec', 'pcm_s16le', 
            '-ar', '16000', 
            '-ac', '1', 
            output_path
        ]
        recovery_result = subprocess.run(recovery_command)
        
        if recovery_result.returncode == 0:
            return {'success': True, 'recovered': True}
    
    return {'success': False, 'error': 'Unrecoverable file'}
```

#### 4.3 React Native 앱 가이드 자동 제공
```python
# 복구 실패 시 상세한 해결 방법 제공
error_details = {
    'error_type': 'moov_atom_missing',
    'user_message': 'moov atom 누락으로 파일이 손상되었습니다.',
    'solution': {
        'react_native_fix': {
            'AudioRecorderPlayer_settings': {
                'AudioEncodingBitRate': 128000,
                'AudioSamplingRate': 44100,
                'AVFormatIDKeyIOS': 'lpcm',
                'OutputFormat': 'wav'
            },
            'proper_stop_sequence': [
                'await AudioRecorderPlayer.stopRecorder()',
                'await new Promise(resolve => setTimeout(resolve, 500))',
                'await AudioRecorderPlayer.release()'
            ]
        }
    }
}
```

#### 4.4 혁신성
✅ **2단계 복구 알고리즘**: 일반 변환 실패 시 자동으로 복구 모드 진입  
✅ **ffmpeg 옵션 최적화**: `-err_detect ignore_err`로 손상 부분 건너뛰기  
✅ **개발자 가이드 자동 생성**: React Native 앱 설정 오류 자동 진단 및 해결책 제시  
✅ **WAV 표준 변환**: 16kHz, 모노, PCM 16bit로 통일하여 호환성 보장  

---

### 5. **동일 화자 추적 시스템 (Identifier)**

#### 5.1 Identifier 규칙
```python
identifier_validator = RegexValidator(
    regex=r'^[CSA]\d{5}$',
    message='C, S, 혹은 A로 시작하고 5자리 숫자가 뒤따라야 합니다.'
)

# 예시:
# C12345 → Child (아동) 화자 12345번
# S29895 → Senior (성인) 화자 29895번  
# A50606 → Auditory (청각장애) 화자 50606번
```

#### 5.2 통합 조회 기능
```python
# views.py
def identifier_audio_list(request, identifier):
    """동일 identifier를 가진 모든 녹음 조회"""
    audios = AudioRecord.objects.filter(
        identifier=identifier
    ).order_by('-created_at')
    
    # 통계 정보
    total_duration = sum([a.duration for a in audios if a.duration])
    avg_snr = audios.aggregate(Avg('snr_mean'))['snr_mean__avg']
    
    return render(request, 'identifier_audio_list.html', {
        'identifier': identifier,
        'audios': audios,
        'total_duration': total_duration,
        'avg_snr': avg_snr
    })
```

#### 5.3 혁신성
✅ **종단간 추적**: 동일 화자의 시간에 따른 음성 변화 추적 가능  
✅ **카테고리 자동 매핑**: Identifier 첫 글자로 카테고리 자동 분류  
✅ **통계 집계**: 화자별 총 녹음 시간, 평균 SNR 등 자동 계산  
✅ **연구 활용**: 종단 연구(longitudinal study)에 최적화된 데이터 구조  

---

### 6. **모바일-웹 통합 RESTful API**

#### 6.1 주요 엔드포인트
```
POST   /api/upload/                    # 파일 업로드 + 메타데이터
GET    /api/audio/category/{category}/ # 카테고리별 목록
GET    /api/audio/{id}/                # 개별 파일 정보
PUT    /api/audio/{id}/                # 메타데이터 수정
POST   /api/transcribe/{id}/           # Whisper 전사 트리거
GET    /api/alignment/{id}/            # WhisperX alignment 결과
POST   /api/background-noise/          # 배경소음 측정 데이터
```

#### 6.2 메타데이터 자동 추출
```python
# React Native에서 전송한 JSON을 자동 파싱
metadata = json.loads(request.data.get('metadata_json'))

# 카테고리별 자동 분류
if 'metainfo_child' in metadata:
    category = 'child'
    metainfo = metadata['metainfo_child']
    age_in_months = metainfo.get('ageInMonths')
    
elif 'metainfo_senior' in metadata:
    category = 'senior'
    metainfo = metadata['metainfo_senior']
    education = metainfo.get('education')
    cognitive_decline = metainfo.get('cognitiveDecline')

elif 'metainfo_auditory' in metadata:
    category = 'auditory'
    metainfo = metadata['metainfo_auditory']
    hearing_level = metainfo.get('hearingLevel')
    has_hearing_aid = metainfo.get('hasHearingAid')
```

#### 6.3 파일 업로드 최적화
```python
# 1. 파일 형식 자동 변환
if ext == 'm4a':
    wav_path = convert_m4a_to_wav(original_path, wav_path)

# 2. 메타데이터 JSON 파일 병렬 저장
metadata_path = f"{saved_unique_id}.json"
combined_metadata = {
    'audio': audio_record.to_dict(),
    'category_data': category_data,
    'client_metadata': metadata_parsed
}
with open(metadata_path, 'w') as f:
    json.dump(combined_metadata, f, ensure_ascii=False, indent=2)

# 3. DB 원자성 보장
audio_record.set_category_data(**category_data)
audio_record.save()
```

#### 6.4 혁신성
✅ **멀티파트 업로드**: 오디오 + JSON 메타데이터 동시 전송  
✅ **자동 카테고리 감지**: JSON 구조 분석으로 화자 유형 자동 판별  
✅ **메타데이터 영구 보존**: DB + JSON 파일 이중 저장으로 데이터 손실 방지  
✅ **CORS 설정**: React Native 앱의 크로스 도메인 요청 지원  

---

### 7. **대시보드 기반 통계 분석 시스템**

#### 7.1 Identifier 기반 화자 그룹핑
```python
# views.py - dashboard()
def dashboard(request):
    """화자(Identifier) 기반 통계 대시보드"""
    
    # 1. 고유 화자 추출 (중복 제거)
    identifiers = AudioRecord.objects.values('identifier').distinct()
    
    speaker_info = {}
    for item in identifiers:
        identifier = item['identifier']
        first_record = AudioRecord.objects.filter(
            identifier=identifier
        ).first()
        
        # 2. 성별 정규화
        normalized_gender = normalize_gender(first_record.gender)
        
        speaker_info[identifier] = {
            'identifier': identifier,
            'category': first_record.category,
            'gender': normalized_gender,
            'region': first_record.region,
            'education': first_record.get_category_data('education'),
            'file_count': AudioRecord.objects.filter(
                identifier=identifier
            ).count()
        }
    
    # 3. 카테고리별 통계
    child_speakers = [s for s in speaker_info.values() if s['category'] == 'child']
    senior_speakers = [s for s in speaker_info.values() if s['category'] == 'senior']
    
    return render(request, 'dashboard.html', {
        'total_speakers': len(speaker_info),
        'child_speakers_count': len(child_speakers),
        'senior_speakers_count': len(senior_speakers),
        'gender_distribution': calculate_gender_distribution(speaker_info),
        'region_distribution': calculate_region_distribution(speaker_info)
    })
```

#### 7.2 성별 정규화 알고리즘
```python
def normalize_gender(gender):
    """다양한 형식의 성별 데이터를 통일"""
    if not gender:
        return None
    gender_lower = gender.lower().strip()
    
    # 남성 변형
    if gender_lower in ['남', '남자', 'male', 'm']:
        return '남성'
    # 여성 변형
    elif gender_lower in ['여', '여자', 'female', 'f']:
        return '여성'
    # 미상
    elif gender_lower in ['unknown', '미상', '불명']:
        return '미상'
    
    return gender
```

#### 7.3 Chart.js 기반 시각화
```javascript
// 성별 분포 파이 차트
const genderCtx = document.getElementById('genderChart').getContext('2d');
new Chart(genderCtx, {
    type: 'pie',
    data: {
        labels: ['남성', '여성', '미상'],
        datasets: [{
            data: [{{ male_count }}, {{ female_count }}, {{ unknown_count }}],
            backgroundColor: ['#007bff', '#dc3545', '#6c757d']
        }]
    }
});

// 지역별 분포 바 차트
const regionCtx = document.getElementById('regionChart').getContext('2d');
new Chart(regionCtx, {
    type: 'bar',
    data: {
        labels: {{ region_labels|safe }},
        datasets: [{
            label: '화자 수',
            data: {{ region_counts|safe }},
            backgroundColor: '#28a745'
        }]
    }
});
```

#### 7.4 혁신성
✅ **화자 중심 통계**: 파일 수가 아닌 고유 화자 수 기반 집계  
✅ **성별 정규화**: 6가지 이상의 성별 표기 자동 통일  
✅ **실시간 갱신**: 페이지 로드 시 SQLite DB 연결 초기화로 최신 데이터 보장  
✅ **다차원 시각화**: 파이/바/라인 차트로 다양한 관점 제공  

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                  React Native Mobile App                     │
│  - 음성 녹음 (react-native-audio-recorder-player)           │
│  - SNR 실시간 측정                                           │
│  - 메타데이터 입력 폼 (카테고리별 동적 생성)                 │
│  - JSON 메타데이터 생성                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS POST /api/upload/
                       │ (Multipart: audio + JSON)
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                    Django Backend Server                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. 파일 수신 및 검증                                  │  │
│  │    - M4A → WAV 변환 (손상 파일 복구 포함)            │  │
│  │    - 메타데이터 JSON 파싱                            │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 2. 메타데이터 처리                                    │  │
│  │    - 카테고리 자동 감지 (metainfo_child/senior/...)  │  │
│  │    - Identifier 검증 (C/S/A + 5자리)                 │  │
│  │    - category_specific_data JSON 구성                │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 3. 데이터베이스 저장                                  │  │
│  │    - AudioRecord 모델에 저장                          │  │
│  │    - JSON 메타데이터 파일 별도 저장                  │  │
│  │    - 인덱스 필드 자동 생성 (성능 최적화)             │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 4. Whisper AI 전사 (비동기)                           │  │
│  │    - 모델 싱글톤 로딩                                 │  │
│  │    - transcript 필드 저장 (읽기 전용)                │  │
│  │    - WhisperX alignment (단어 타임스탬프)            │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────┬─────────────────────────────────────────┘
                    │ 
                    ↓
┌─────────────────────────────────────────────────────────────┐
│                      Web Dashboard                           │
│  - 화자별 통계 (Identifier 그룹핑)                          │
│  - SNR 분포 차트                                             │
│  - 카테고리별 분석 (아동/성인/청각장애)                     │
│  - WaveSurfer.js 파형 시각화                                │
│  - 전사 내용 수동 편집 (manual_transcript)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 데이터 모델 구조

### 핵심 테이블: AudioRecord

```sql
CREATE TABLE voice_app_audiorecord (
    -- 기본 정보
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier VARCHAR(6) CHECK(identifier REGEXP '^[CSA]\d{5}$'),
    category VARCHAR(20) CHECK(category IN ('child','senior','atypical','auditory','normal')),
    
    -- 파일 정보
    audio_file VARCHAR(100) NOT NULL,  -- 경로: audio/{category}/{filename}
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    
    -- 화자 기본 정보
    name VARCHAR(100),
    gender VARCHAR(10),
    birth_year VARCHAR(4),
    birth_month VARCHAR(2),
    birth_day VARCHAR(2),
    age VARCHAR(3),  -- 자동 계산
    
    -- 녹음 환경
    recording_location VARCHAR(50),
    noise_level VARCHAR(20),
    device_type VARCHAR(30),
    has_microphone VARCHAR(10),
    region VARCHAR(20) INDEX,
    
    -- 카테고리별 특화 필드 (인덱싱 최적화)
    education_level INTEGER INDEX,      -- Senior/Auditory
    hearing_level VARCHAR(30) INDEX,    -- Auditory
    age_in_months INTEGER,              -- Child/Auditory
    diagnosis VARCHAR(100),
    
    -- JSON 확장 필드
    category_specific_data TEXT CHECK(JSON_VALID(category_specific_data)),
    
    -- AI 전사
    transcript TEXT,                    -- Whisper 자동 전사 (읽기 전용)
    manual_transcript TEXT,             -- 수동 보정 전사
    status VARCHAR(20) CHECK(status IN ('unprocessed','processing','completed','failed')),
    
    -- WhisperX Alignment
    alignment_data TEXT CHECK(JSON_VALID(alignment_data)),
    alignment_status VARCHAR(20),
    
    -- 음질 분석
    snr_mean REAL,
    snr_max REAL,
    snr_min REAL,
    
    -- 메타 정보
    data_source VARCHAR(20) CHECK(data_source IN ('mobile_app','django_admin','api_upload'))
);
```

---

## 🔐 특허 청구 범위 (주요 청구항)

### 청구항 1 (독립항)
음성 데이터 수집 및 관리 시스템에 있어서,

(a) 모바일 단말에서 화자의 음성을 녹음하고 화자 카테고리에 따라 상이한 메타데이터를 입력받는 데이터 수집 모듈;

(b) 상기 음성 파일 및 메타데이터를 서버로 전송하고, 서버는 상기 메타데이터를 분석하여 화자 카테고리(아동, 성인, 청각장애, 음성장애, 일반)를 자동으로 분류하는 카테고리 감지 모듈;

(c) 상기 분류된 카테고리에 따라 JSON 기반의 확장 가능한 스키마를 적용하여 메타데이터를 저장하되, 자주 쿼리되는 필드는 별도의 인덱스 컬럼으로 추출하여 검색 성능을 최적화하는 적응형 저장 모듈;

(d) 상기 음성 파일을 Whisper AI 모델로 자동 전사하여 읽기 전용 전사 필드(transcript)에 저장하고, 사용자의 수동 보정 내용은 별도의 수정 가능 필드(manual_transcript)에 저장하는 이중 전사 모듈;

(e) 상기 음성 파일의 SNR(Signal-to-Noise Ratio)을 평균, 최대, 최소값으로 자동 측정하여 저장하고, 임계값 기준으로 품질 등급을 자동 분류하는 품질 분석 모듈;

(f) 손상된 오디오 파일(moov atom 누락 등)을 감지하고, ffmpeg의 오류 무시 옵션을 사용하여 자동 복구 및 표준 포맷(WAV 16kHz 모노)으로 변환하는 파일 복구 모듈;

(g) 동일 화자의 다중 녹음 데이터를 고유 식별자(Identifier: C/S/A + 5자리 숫자)로 추적하고, 시간에 따른 음성 변화를 종단적으로 분석할 수 있도록 통합 조회 기능을 제공하는 화자 추적 모듈;

을 포함하는 것을 특징으로 하는 특수화자 음성 데이터 통합 관리 시스템.

---

### 청구항 2 (종속항)
청구항 1에 있어서,

상기 적응형 저장 모듈은,

- 아동 카테고리의 경우: 월령(age_in_months), 발음 문제 유무, 주관적 평가를 포함하는 메타데이터,
- 성인 카테고리의 경우: 총 교육년수, 인지 저하 여부, 직업 정보를 포함하는 메타데이터,
- 청각장애 카테고리의 경우: 청력 수준(6단계), 보청기 사용 여부 및 기간, 청력 손실 기간을 포함하는 메타데이터,

를 각각 JSON 필드에 저장하되, 교육년수(education_level), 청력 수준(hearing_level), 월령(age_in_months)은 별도의 인덱스 컬럼으로 추출하여 관리하는 것을 특징으로 하는 시스템.

---

### 청구항 3 (종속항)
청구항 1에 있어서,

상기 이중 전사 모듈은,

WhisperX 모델을 사용하여 음성 파일의 자동 전사 시 단어 단위의 시작/종료 타임스탬프를 생성하고, 이를 alignment_data JSON 필드에 저장하여 정밀한 음성-텍스트 정렬 정보를 제공하는 것을 특징으로 하는 시스템.

---

### 청구항 4 (종속항)
청구항 1에 있어서,

상기 품질 분석 모듈은,

SNR 평균값을 기준으로,
- 20dB 초과: 우수 등급,
- 15~20dB: 양호 등급,
- 10~15dB: 보통 등급,
- 10dB 미만: 불량 등급(재녹음 권장),

으로 자동 분류하고, 대시보드에서 SNR 분포 차트를 제공하는 것을 특징으로 하는 시스템.

---

### 청구항 5 (종속항)
청구항 1에 있어서,

상기 파일 복구 모듈은,

1차 변환 실패 시 "moov atom not found" 오류를 감지하면,
2차로 ffmpeg의 `-err_detect ignore_err` 옵션을 적용하여 손상 부분을 건너뛰고 복구 가능한 오디오 데이터만 추출하며,
복구 실패 시 React Native 앱의 MediaRecorder 설정 오류를 자동 진단하고 해결 가이드를 JSON 형태로 반환하는 것을 특징으로 하는 시스템.

---

### 청구항 6 (종속항)
청구항 1에 있어서,

상기 화자 추적 모듈은,

정규 표현식 `^[CSA]\d{5}$`을 사용하여 Identifier의 유효성을 검증하고,
- C로 시작: Child(아동),
- S로 시작: Senior(성인),
- A로 시작: Auditory(청각장애),

로 자동 매핑하며, 동일 Identifier를 가진 모든 녹음의 총 재생 시간, 평균 SNR, 녹음 횟수를 자동 집계하여 제공하는 것을 특징으로 하는 시스템.

---

### 청구항 7 (방법 청구항)
음성 데이터를 수집하고 관리하는 방법에 있어서,

(S1) 모바일 앱에서 화자 카테고리를 선택받고, 해당 카테고리에 맞는 메타데이터 입력 폼을 동적으로 생성하는 단계;

(S2) 음성 녹음 후 SNR을 실시간 측정하고, 음성 파일과 메타데이터 JSON을 서버로 전송하는 단계;

(S3) 서버에서 메타데이터 JSON의 구조를 분석하여 화자 카테고리를 자동 감지하는 단계;

(S4) 음성 파일의 형식을 검증하고, 손상된 파일인 경우 자동 복구를 시도하며, 복구 성공 시 WAV 표준 포맷으로 변환하는 단계;

(S5) 메타데이터를 카테고리별 JSON 스키마에 따라 저장하되, 자주 쿼리되는 필드는 인덱스 컬럼으로 추출하는 단계;

(S6) Whisper AI 모델을 사용하여 음성을 자동 전사하고, 전사 결과를 읽기 전용 필드에 저장하는 단계;

(S7) 사용자가 전사 내용을 수정하는 경우, 수정 내용을 별도의 수정 가능 필드에 저장하는 단계;

(S8) 동일 화자의 Identifier를 기준으로 다중 녹음 데이터를 그룹핑하여 통계를 생성하는 단계;

를 포함하는 것을 특징으로 하는 음성 데이터 관리 방법.

---

## 🎓 선행 기술 대비 진보성

| 비교 항목 | 선행 기술 | 본 발명 | 진보성 |
|---------|---------|---------|--------|
| **메타데이터 관리** | 고정된 필드 구조 | JSON 기반 확장 가능 스키마 + 인덱스 최적화 | ⭐⭐⭐ |
| **전사 시스템** | 단일 필드에 덮어쓰기 | AI 자동 전사 + 수동 보정 이중 구조 | ⭐⭐⭐ |
| **품질 관리** | 사후 수동 측정 | 실시간 SNR 자동 측정 + 등급 자동 분류 | ⭐⭐⭐ |
| **파일 복구** | 수동 처리 | 2단계 자동 복구 + 개발자 가이드 생성 | ⭐⭐⭐ |
| **화자 추적** | 파일명 기반 (비표준) | Identifier 기반 표준화 + 정규식 검증 | ⭐⭐⭐ |
| **카테고리 분류** | 수동 선택 | JSON 구조 분석을 통한 자동 감지 | ⭐⭐ |
| **성별 정규화** | 통일되지 않음 | 6가지 이상 표기 자동 통일 알고리즘 | ⭐⭐ |

---

## 💼 산업상 이용 가능성

### 1. 음성 장애 진단 및 치료
- **아동 언어 발달 평가**: 월령별 발화 데이터 축적으로 발달 지연 조기 발견
- **노인성 음성 장애 모니터링**: 종단 연구로 퇴행 속도 추적
- **청각 장애 재활**: 보청기 착용 전후 음성 변화 정량 분석

### 2. 음성 인식 AI 학습 데이터
- **특수화자 음성 코퍼스 구축**: 카테고리별 메타데이터로 세분화된 학습 데이터
- **노이즈 환경 대응**: SNR 기반 품질 필터링으로 고품질 데이터 선별
- **시간 정렬 데이터**: WhisperX alignment로 정밀한 음소 단위 학습

### 3. 원격 의료 플랫폼
- **비대면 진단**: 모바일 앱 녹음 + 자동 전사로 원격 음성 평가
- **품질 보증**: SNR 임계값 미달 시 재녹음 자동 요청
- **데이터 표준화**: Identifier 기반 환자 추적으로 의료 기록 통합

### 4. 연구 기관
- **다기관 공동 연구**: 표준화된 메타데이터로 데이터 통합 용이
- **종단 연구**: 동일 화자의 시간별 변화 추적
- **빅데이터 분석**: JSON 확장 스키마로 새로운 변수 추가 가능

---

## 📈 기대 효과

### 1. 기술적 효과
✅ **데이터 품질 향상**: SNR 기반 자동 품질 관리로 불량 데이터 사전 차단  
✅ **수집 효율성 증대**: 모바일 앱 통합으로 현장 녹음 즉시 서버 전송  
✅ **전사 정확도 개선**: AI 자동 전사 + 수동 보정 이중 시스템으로 오류율 최소화  
✅ **확장성 확보**: JSON 스키마로 새로운 화자 카테고리 추가 용이  

### 2. 경제적 효과
✅ **전사 비용 절감**: 수작업 전사 대비 Whisper AI로 70% 이상 비용 절감  
✅ **데이터 손실 방지**: 파일 복구 알고리즘으로 재녹음 비용 절감  
✅ **연구 기간 단축**: 표준화된 메타데이터로 데이터 정제 시간 감소  

### 3. 사회적 효과
✅ **의료 접근성 향상**: 원격 음성 진단으로 지역/시간 제약 해소  
✅ **장애인 지원**: 청각장애/음성장애인 맞춤형 데이터 수집 및 분석  
✅ **연구 활성화**: 고품질 공개 데이터셋 제공으로 학계 기여  

---

## 🔬 실시예

### 실시예 1: 아동 언어 발달 평가
```
[입력]
- 화자: C12345 (4세 아동, 36개월)
- 녹음: "강아지가 뛰어가요" (3초)
- SNR: 평균 18.5dB, 최대 23.1dB, 최소 14.2dB
- 메타데이터: {
    "ageInMonths": 36,
    "pronunciationProblem": "없음",
    "place": "가정"
  }

[처리 과정]
1. 카테고리 자동 감지: metainfo_child 존재 → category='child'
2. Identifier 검증: C12345 → 유효
3. SNR 품질 등급: 18.5dB → 양호
4. Whisper 전사: "강아지가 뛰어가요"
5. WhisperX alignment:
   - "강아지가": 0.0~0.8초
   - "뛰어가요": 0.8~2.1초

[출력]
- DB 저장: AudioRecord(id=1, identifier='C12345', category='child', ...)
- JSON 파일: C12345_20250127_001.json
- 대시보드: "아동 화자 1명, 녹음 1건, 평균 SNR 18.5dB"
```

### 실시예 2: 손상 파일 복구
```
[입력]
- 파일: recording_broken.m4a (moov atom 누락)
- 크기: 2.3MB
- 원인: React Native 앱 강제 종료

[처리 과정]
1. 1차 변환 시도: ffmpeg -i recording_broken.m4a output.wav
   → 실패: "moov atom not found"

2. 2차 복구 모드: ffmpeg -err_detect ignore_err -i recording_broken.m4a output.wav
   → 성공: 2.1초 오디오 복구 (손상 부분 0.2초 제외)

3. 개발자 가이드 생성:
   {
     "error_type": "moov_atom_missing",
     "solution": {
       "react_native_fix": {
         "proper_stop_sequence": [
           "await AudioRecorderPlayer.stopRecorder()",
           "await new Promise(resolve => setTimeout(resolve, 500))",
           "await AudioRecorderPlayer.release()"
         ]
       }
     }
   }

[출력]
- 복구된 파일: output.wav (16kHz, 모노, 2.1초)
- 서버 응답: {"success": true, "recovered": true, "duration": 2.1}
```

### 실시예 3: 동일 화자 종단 분석
```
[입력]
- Identifier: S29895 (65세 성인)
- 녹음 데이터:
  * 2024-01-15: "산책을 다녀왔습니다" (SNR 20.1dB)
  * 2024-06-20: "건강검진을 받았어요" (SNR 19.3dB)
  * 2025-01-27: "오늘 날씨가 좋네요" (SNR 17.8dB)

[처리 과정]
1. Identifier 필터링: AudioRecord.objects.filter(identifier='S29895')
2. 통계 집계:
   - 총 녹음 횟수: 3건
   - 총 재생 시간: 8.7초
   - 평균 SNR: (20.1 + 19.3 + 17.8) / 3 = 19.07dB
   - SNR 추세: 하락 경향 (-2.3dB/년)

[출력]
- 대시보드 차트: SNR 시간별 라인 그래프 (하락 추세 시각화)
- 알림: "SNR 하락 감지 - 녹음 환경 또는 음성 건강 확인 필요"
```

---

## 📚 참고 문헌

1. **Whisper AI**: Radford, A., et al. (2022). "Robust Speech Recognition via Large-Scale Weak Supervision." arXiv:2212.04356
2. **WhisperX**: Bain, M., et al. (2023). "WhisperX: Time-Accurate Speech Transcription of Long-Form Audio." INTERSPEECH 2023
3. **SNR Measurement**: ITU-T Recommendation P.56 (2011). "Objective measurement of active speech level"
4. **Audio Quality Standards**: ITU-R BS.1116-3 (2015). "Methods for the subjective assessment of small impairments in audio systems"
5. **Django Framework**: Django Software Foundation (2024). "Django Documentation v4.2"

---

## 📞 발명자 정보

**발명의 명칭**: 다중 화자 카테고리 기반의 음성 데이터 수집, 분석 및 품질 관리 통합 시스템

**출원인**: [귀하의 기관/회사명]

**발명자**: [귀하의 성명]

**우선권 주장**: 대한민국 (KR)

**기술 분류**:
- IPC: G10L 15/26 (음성 인식)
- IPC: G10L 25/00 (음성 분석)
- IPC: H04M 1/60 (음성 녹음)

**키워드**: 
음성 인식, 메타데이터 관리, SNR 측정, Whisper AI, 특수화자, 음성 품질 분석, 파일 복구, 종단 연구, React Native, Django

---

## 📄 도면 목록

1. **도면 1**: 시스템 전체 아키텍처 (모바일 앱 - 서버 - 대시보드)
2. **도면 2**: 데이터베이스 ERD (AudioRecord 테이블 구조)
3. **도면 3**: 카테고리별 메타데이터 JSON 스키마
4. **도면 4**: 이중 전사 시스템 흐름도 (Whisper → transcript, 수동 → manual_transcript)
5. **도면 5**: SNR 측정 및 품질 등급 분류 알고리즘
6. **도면 6**: 손상 파일 복구 프로세스 (2단계 복구)
7. **도면 7**: Identifier 기반 화자 추적 및 통계 집계
8. **도면 8**: 대시보드 화면 구성 (파이 차트, 바 차트, 테이블)
9. **도면 9**: React Native 앱 화면 (카테고리별 입력 폼)
10. **도면 10**: WhisperX Alignment 데이터 구조

---

## 🎯 특허 전략 제언

### 1. 핵심 청구항 강화
- **카테고리 적응형 스키마**: JSON 기반 확장 구조 + 인덱스 최적화 조합
- **이중 전사 시스템**: AI 자동 + 수동 보정 분리 구조
- **2단계 파일 복구**: 일반 변환 → 복구 모드 자동 전환

### 2. 방어적 청구항 추가
- 성별 정규화 알고리즘 (6가지 이상 표기 통일)
- Identifier 정규식 검증 (C/S/A + 5자리)
- SNR 4단계 품질 등급 분류

### 3. 국제 출원 고려
- PCT 출원: 미국, 유럽, 일본, 중국
- 우선심사 신청: 의료기기/AI 분야 산업 활용도 높음

### 4. 선행 기술 조사 키워드
- "speech data collection system"
- "metadata management JSON schema"
- "Whisper ASR transcription"
- "audio quality SNR measurement"
- "damaged audio file recovery"
- "speaker tracking identifier"

---

## ✅ 체크리스트

특허 출원 전 확인 사항:
- [ ] 선행 기술 조사 완료 (KIPRIS, Google Patents)
- [ ] 도면 10종 준비 (시스템 구성도, 흐름도, ERD 등)
- [ ] 실시예 3개 이상 작성
- [ ] 청구항 독립항 1개 + 종속항 6개 이상
- [ ] 명세서 배경, 과제, 효과 구체적 기술
- [ ] 소스 코드 공개 여부 결정 (오픈소스 vs 영업비밀)
- [ ] 공동 발명자 확인 (모바일 앱 개발자 포함 여부)
- [ ] 출원 비용 예산 확보 (국내: ~200만원, PCT: ~1000만원)

---

**작성일**: 2025년 1월 27일  
**버전**: v1.0  
**문서 유형**: 발명 특허 기술 설명서  
**기밀 등급**: 대외비 (출원 전까지 외부 유출 금지)  

---

## 💬 연락처

특허 관련 문의:  
📧 Email: [귀하의 이메일]  
📞 Tel: [귀하의 연락처]  
🏢 소속: [귀하의 기관/회사명]  

기술 지원:  
🔗 GitHub: https://github.com/exphon/voice_project  
📖 문서: /var/www/html/dj_voice_manage/README.md  
