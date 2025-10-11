# Whisper 전사 기능 수정 완료 및 테스트 가이드

## 🔧 수정 사항

### 1. **문제 원인**
- `whisperx` 모듈이 설치되지 않아 서버 시작 실패
- `voice_app/views.py`의 `from .tasks import transcribe_audio_task` import 실패

### 2. **해결 방법**
- `whisper_utils.py`를 수정하여 `whisperx`를 선택적 의존성으로 변경
- `whisperx`가 없어도 기본 Whisper는 정상 작동하도록 수정

### 3. **수정된 파일**
1. **voice_app/views.py**
   - `transcribe_single_audio` 함수에 상세 로깅 추가
   - 파일 존재 여부 확인 로직 추가
   - 오류 추적을 위한 traceback 추가

2. **voice_app/tasks.py**
   - 전사 프로세스의 각 단계에 로깅 추가
   - 파일 경로, 크기 등 상세 정보 출력

3. **voice_app/whisper_utils.py**
   - `whisperx` import를 try/except로 감싸서 선택적으로 처리
   - `WHISPERX_AVAILABLE` 플래그 추가
   - `get_whisperx_model()`과 `transcribe_and_align_whisperx()`에 가용성 체크 추가

---

## ✅ 현재 상태

**서버 상태:** ✅ 정상 실행 중
- 주소: `210.125.93.241:8010`
- Whisper 모델: ✅ 로드 완료 (base 모델)
- WhisperX: ⚠️ 사용 불가 (미설치), 기본 Whisper 사용

**로그 출력:**
```
[WhisperX] WhisperX module not available, using basic Whisper only
[Whisper] Loading model...
[Whisper] Model loaded successfully.
```

---

## 🧪 테스트 방법

### 1. 브라우저에서 테스트

1. **오디오 상세 페이지 접속**
   ```
   http://210.125.93.241:8010/voice/audio/<audio_id>/
   ```
   (예: `http://210.125.93.241:8010/voice/audio/1/`)

2. **Whisper 전사 버튼 클릭**
   - "🧠 Whisper 전사" 버튼 클릭
   - 페이지가 리로드되면서 메시지 표시

3. **결과 확인**
   - 성공 시: "Whisper 전사가 완료되었습니다." 메시지와 함께 전사 내용이 "전사 내용" 섹션에 표시됨
   - 실패 시: 오류 메시지 표시

### 2. 터미널에서 로그 확인

다른 터미널 창에서 실시간 로그 모니터링:

```bash
cd /var/www/html/dj_voice_manage
tail -f django_server.log | grep -i "\[transcribe\]\|\[task\]\|\[whisper\]"
```

**예상 로그 출력 (성공 시):**
```
[Transcribe] Starting transcription for audio ID: 1
[Transcribe] Audio file path: /var/www/html/dj_voice_manage/media/audio/...
[Transcribe] Status set to 'processing' for audio ID: 1
[Transcribe] Calling transcribe_audio_task for ID: 1
[Task] transcribe_audio_task started for audio ID: 1
[Task] AudioRecord found: ID=1
[Task] Status set to 'processing'
[Task] Audio file path: /var/www/html/dj_voice_manage/media/audio/...
[Task] Audio file exists, size: XXXXX bytes
[Task] Calling transcribe_audio()...
[Whisper] Transcription completed in X.XX seconds.
[Task] transcribe_audio() returned: 안녕하세요...
[Task Success] Transcription completed for ID 1
[Transcribe] Transcription task completed for ID: 1
[Transcribe Success] Transcription result: 안녕하세요...
```

**예상 로그 출력 (실패 시):**
```
[Transcribe] Starting transcription for audio ID: 1
[Transcribe Error] Audio file not found: /path/to/file.wav
```
또는
```
[Task Error] Exception in transcription for ID 1: ...
```

### 3. 데이터베이스 확인

```bash
# Django shell에서 확인
cd /var/www/html/dj_voice_manage
python3 manage.py shell
```

```python
from voice_app.models import AudioRecord

# 특정 오디오 레코드 확인
audio = AudioRecord.objects.get(id=1)
print(f"Status: {audio.status}")
print(f"Transcription: {audio.transcription}")
```

---

## 📊 예상 결과

### 성공 케이스
- **상태(status):** `'completed'`
- **전사 내용(transcription):** 한국어 텍스트 (예: "안녕하세요 테스트입니다")
- **처리 시간:** 오디오 길이에 따라 다름 (보통 실시간의 0.1~0.5배)

### 실패 케이스 (가능한 원인)

1. **오디오 파일 없음**
   - 로그: `[Transcribe Error] No audio file for ID X`
   - 해결: 오디오 파일이 올바르게 업로드되었는지 확인

2. **파일 경로 문제**
   - 로그: `[Task Error] Audio file does not exist`
   - 해결: media 폴더 권한 및 파일 존재 확인

3. **Whisper 모델 미로드**
   - 로그: `[Whisper Error] Model not loaded`
   - 해결: 서버 재시작 또는 Whisper 재설치

4. **메모리 부족**
   - 로그: `CUDA out of memory` 또는 시스템 오류
   - 해결: 더 작은 모델 사용 (tiny, small) 또는 CPU 모드

---

## 🔍 문제 해결 체크리스트

### 전사 시작 전 확인사항:

- [ ] 서버가 정상 실행 중인가? (`ps aux | grep runserver`)
- [ ] Whisper 모델이 로드되었나? (로그에서 `[Whisper] Model loaded successfully.` 확인)
- [ ] 오디오 파일이 존재하는가?
- [ ] 오디오 파일이 지원되는 형식인가? (.wav, .mp3, .m4a 등)

### 전사 실패 시 확인사항:

1. **로그 확인**
   ```bash
   tail -100 django_server.log | grep -i "error\|exception\|fail"
   ```

2. **오디오 파일 확인**
   ```bash
   ls -lh /var/www/html/dj_voice_manage/media/audio/
   ```

3. **Whisper 모델 상태 확인**
   ```bash
   python3 -c "import whisper; m=whisper.load_model('base'); print('OK')"
   ```

4. **상태 초기화 (필요시)**
   ```bash
   cd /var/www/html/dj_voice_manage
   python3 manage.py shell
   ```
   ```python
   from voice_app.models import AudioRecord
   AudioRecord.objects.filter(status='processing').update(status='pending')
   ```

---

## 💡 추가 개선 사항 (옵션)

### 1. WhisperX 설치 (고급 기능)
WhisperX는 word-level alignment를 제공하여 더 정확한 타임스탬프를 제공합니다.

```bash
pip install whisperx
```

설치 후 서버 재시작하면 자동으로 WhisperX 사용

### 2. 더 큰 모델 사용 (정확도 향상)
`whisper_utils.py` Line 23에서 모델 크기 변경:
- `tiny`: 가장 빠름, 정확도 낮음
- `base`: 현재 사용 중 (균형)
- `small`: 더 정확, 약간 느림
- `medium`: 매우 정확, 느림
- `large`: 최고 정확도, 매우 느림

```python
model = whisper.load_model("small")  # base → small
```

### 3. 비동기 처리 (Celery)
현재는 동기 방식이라 전사 완료까지 페이지가 대기합니다.
Celery를 설정하면 백그라운드에서 처리 가능합니다.

---

## 📝 테스트 시나리오

### 시나리오 1: 짧은 오디오 (5초 미만)
1. 5초 이하의 짧은 음성 파일 업로드
2. Whisper 전사 버튼 클릭
3. 예상: 즉시 완료 (1-2초)

### 시나리오 2: 중간 길이 오디오 (10-30초)
1. 10-30초 음성 파일 업로드
2. Whisper 전사 버튼 클릭
3. 예상: 5-10초 소요

### 시나리오 3: 긴 오디오 (1분 이상)
1. 1분 이상 음성 파일 업로드
2. Whisper 전사 버튼 클릭
3. 예상: 20-60초 소요

---

## 🎯 성공 기준

✅ **전사 성공으로 간주하는 조건:**
1. 상태가 `'completed'`로 변경됨
2. `transcription` 필드에 한국어 텍스트가 채워짐
3. 전사 내용이 오디오 내용과 일치함
4. 로그에 에러가 없음

⚠️ **부분 성공 (개선 필요):**
1. 전사는 되었으나 정확도가 낮음 → 더 큰 모델 사용 고려
2. 특정 단어가 누락됨 → 음질 문제 또는 배경 소음

❌ **실패:**
1. 상태가 `'failed'`로 변경됨
2. 오류 메시지 표시
3. transcription이 비어있음

---

## 📞 지원

문제 발생 시 다음 정보를 제공해주세요:

1. **오디오 ID**: 전사하려는 오디오의 ID 번호
2. **오류 메시지**: 브라우저에 표시된 오류
3. **로그**: `tail -100 django_server.log`의 출력
4. **오디오 정보**: 파일 형식, 길이, 크기

---

**테스트 시작:**
```bash
# 로그 모니터링 시작
tail -f django_server.log | grep -i "\[transcribe\]\|\[task\]\|\[whisper\]"
```

그 다음 브라우저에서 Whisper 전사 버튼을 클릭하세요!
