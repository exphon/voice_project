# Speaker Diarization (화자 분리) 기능 가이드

## 개요

Pyannote.audio를 사용하여 오디오 파일에서 여러 화자를 자동으로 분리하는 기능입니다. 아동 음성 데이터에서 선생님과 아동의 발화를 구분할 수 있습니다.

## 주요 기능

1. **자동 화자 감지**: 오디오에서 1-2명의 화자를 자동으로 감지
2. **화자별 레이블링**: 발화량 기준으로 "아동", "선생님" 자동 할당
3. **타임라인 시각화**: 화자별 발화 구간을 타임라인으로 표시
4. **통계 정보**: 화자별 발화 시간, 세그먼트 수, 비율 표시
5. **화자별 오디오 추출**: 특정 화자의 발화만 별도 파일로 추출

## 설치 및 설정

### 1. Pyannote 패키지 확인

이미 설치되어 있음:
```bash
conda list | grep pyannote
# pyannote-audio            3.3.2
# pyannote-core             5.0.0
# pyannote-pipeline         3.0.1
```

### 2. Hugging Face 토큰 설정

Pyannote 모델을 사용하려면 Hugging Face 계정과 토큰이 필요합니다.

#### 2.1 Hugging Face 계정 생성 및 토큰 발급
1. https://huggingface.co/ 에서 계정 생성
2. Settings > Access Tokens에서 토큰 생성
3. 토큰 타입: "Read" 권한

#### 2.2 Pyannote 모델 접근 권한 신청
다음 모델에 대한 접근 권한을 신청해야 합니다:
- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://huggingface.co/pyannote/segmentation-3.0

각 모델 페이지에서 "Agree and access repository" 클릭

#### 2.3 환경 변수 설정

**방법 1: 환경 변수로 설정 (권장)**
```bash
# ~/.bashrc 또는 ~/.bash_profile에 추가
export HUGGINGFACE_TOKEN="your_token_here"

# 적용
source ~/.bashrc
```

**방법 2: Django settings.py에서 설정**
```python
# voice_project/settings.py
HUGGINGFACE_TOKEN = 'your_token_here'
```

**방법 3: 코드에서 직접 전달**
```python
# diarization_utils.py에서 토큰 하드코딩 (비권장)
diarizer = SpeakerDiarizer(use_auth_token='your_token_here')
```

### 3. 서버 재시작
```bash
pkill -f "manage.py runserver"
cd /var/www/html/dj_voice_manage
nohup python manage.py runserver 0.0.0.0:8010 > django_server.log 2>&1 &
```

## 사용 방법

### 웹 인터페이스

1. **오디오 상세 페이지 접속**
   - http://210.125.93.241:8010/audio/
   - 원하는 오디오 레코드 선택

2. **화자 분리 실행**
   - "🎙️ 화자 분리 (Speaker Diarization)" 섹션 찾기
   - "🎙️ 화자 분리 시작" 버튼 클릭
   - 처리 시간: 약 30초 ~ 2분 (오디오 길이에 따라 다름)

3. **결과 확인**
   - 상태: "✅ 화자 분리 완료 (2명)" 표시
   - "👁️ 화자 분리 결과 보기" 버튼 클릭

4. **시각화**
   - **타임라인**: 화자별 발화 구간을 색상으로 구분
   - **통계**: 화자별 발화 시간, 세그먼트 수, 비율
   - **세그먼트**: 화자별 발화 구간 목록 (클릭하면 해당 위치로 이동)

5. **화자별 오디오 추출**
   - "💾 화자별 오디오 추출" 버튼 클릭
   - 원하는 화자 선택 (예: "아동" 또는 "선생님")
   - 추출된 오디오 파일 다운로드

### 프로그래밍 방식 사용

```python
from voice_app.diarization_utils import SpeakerDiarizer

# Diarizer 초기화
diarizer = SpeakerDiarizer()

# 화자 분리 수행
result = diarizer.perform_diarization(
    audio_path='/path/to/audio.wav',
    num_speakers=None,  # None이면 자동 감지
    min_speakers=1,
    max_speakers=2
)

# 결과 확인
print(f"감지된 화자 수: {result['num_speakers']}")
print(f"화자 목록: {result['speakers']}")

# 화자 레이블 할당
result = diarizer.assign_speaker_labels(result)

# 특정 화자 오디오 추출
diarizer.extract_speaker_audio(
    audio_path='/path/to/audio.wav',
    diarization_result=result,
    speaker='아동',
    output_path='/path/to/child_only.wav'
)
```

## 데이터베이스 필드

### AudioRecord 모델에 추가된 필드:

```python
diarization_data = models.JSONField(null=True, blank=True)
# 화자 분리 결과 JSON
# {
#   'segments': [...],
#   'num_speakers': 2,
#   'speakers': ['아동', '선생님'],
#   'speaker_stats': {...},
#   'status': 'completed'
# }

diarization_status = models.CharField(max_length=20)
# 상태: 'unprocessed', 'processing', 'completed', 'failed'

num_speakers = models.IntegerField(null=True, blank=True)
# 감지된 화자 수
```

## API 엔드포인트

### 1. 화자 분리 실행
```
POST /audio/diarize/<audio_id>/
Parameters: num_speakers (optional, int)
Response: {
    'success': true,
    'num_speakers': 2,
    'speakers': ['아동', '선생님'],
    'message': '2명의 화자가 감지되었습니다.'
}
```

### 2. 화자 분리 데이터 조회
```
GET /audio/diarization-data/<audio_id>/
Response: {
    'success': true,
    'data': {
        'num_speakers': 2,
        'speakers': ['아동', '선생님'],
        'speaker_stats': {...},
        'timeline': [...],
        ...
    }
}
```

### 3. 화자 분리 상태 확인
```
GET /audio/diarization-status/<audio_id>/
Response: {
    'status': 'completed',
    'num_speakers': 2,
    'has_diarization_data': true
}
```

### 4. 화자별 오디오 추출
```
POST /audio/extract-speaker/<audio_id>/
Parameters: speaker (string, e.g., '아동')
Response: WAV file download
```

## 결과 데이터 구조

### Diarization Result JSON:

```json
{
    "segments": [
        {
            "start": 0.5,
            "end": 2.3,
            "duration": 1.8,
            "speaker": "아동"
        },
        {
            "start": 2.5,
            "end": 4.1,
            "duration": 1.6,
            "speaker": "선생님"
        }
    ],
    "num_speakers": 2,
    "speakers": ["아동", "선생님"],
    "speaker_stats": {
        "아동": {
            "total_duration": 25.3,
            "num_segments": 15,
            "percentage": 45.2
        },
        "선생님": {
            "total_duration": 30.7,
            "num_segments": 12,
            "percentage": 54.8
        }
    },
    "total_speech_time": 56.0,
    "status": "completed"
}
```

## 주의사항

1. **처리 시간**: GPU 사용 시 약 실시간, CPU만 사용 시 더 오래 걸림
2. **메모리**: 긴 오디오 파일(10분 이상)은 메모리를 많이 사용할 수 있음
3. **정확도**: 화자 간 음성 특성이 유사하면 정확도가 떨어질 수 있음
4. **최적 조건**:
   - 화자 수: 1-2명 (아동 데이터 최적화)
   - 오디오 품질: 높을수록 좋음
   - 배경 소음: 적을수록 좋음

## 트러블슈팅

### 1. Hugging Face 인증 오류
```
Error: Access token is required
```
**해결**: Hugging Face 토큰 설정 확인 (위 "설치 및 설정" 참조)

### 2. 모델 접근 권한 오류
```
Error: Repository not found or access denied
```
**해결**: Hugging Face에서 pyannote 모델 접근 권한 신청

### 3. GPU 메모리 부족
```
Error: CUDA out of memory
```
**해결**: 
- 더 짧은 오디오 파일로 테스트
- CPU 모드 사용 (자동 fallback됨)

### 4. 화자 감지 실패
```
num_speakers: 0
```
**해결**:
- 오디오 파일 품질 확인
- min_speakers, max_speakers 파라미터 조정
- 배경 소음 제거

## 성능 최적화

### GPU 사용 (권장)
```python
# 자동으로 GPU 감지 및 사용
# torch.cuda.is_available() == True 확인
```

### 배치 처리
```python
# 여러 파일 처리 시
diarizer = SpeakerDiarizer()  # 한 번만 초기화
for audio_file in audio_files:
    result = diarizer.perform_diarization(audio_file)
```

## 참고 자료

- Pyannote.audio 공식 문서: https://github.com/pyannote/pyannote-audio
- Hugging Face 모델 카드: https://huggingface.co/pyannote/speaker-diarization-3.1
- 논문: Bredin et al., "Pyannote.audio 2.1 speaker diarization pipeline" (2023)

## 문의

기술 지원이 필요한 경우:
- GitHub Issues: https://github.com/pyannote/pyannote-audio/issues
- Django 애플리케이션 로그: `/var/www/html/dj_voice_manage/django_server.log`
