# Whisper 전사 기능 검토 보고서

## 📋 검토 일시
2025-10-11

## 🔍 검토 대상
`audio_detail.html`의 "Whisper 전사" 버튼 기능

## ⚠️ 발견된 문제

### 1. **심각한 문제: tasks.py import가 주석 처리됨**

**위치:** `voice_app/views.py` Line 47
```python
# from .tasks import transcribe_audio_task  # whisperx 의존성 때문에 임시 주석
```

**영향:** 
- `transcribe_single_audio` 뷰에서 `transcribe_audio_task(audio.id)` 호출 시 **NameError 발생**
- Whisper 전사 버튼을 클릭하면 **오류 발생**하여 전사가 진행되지 않음

**원인:**
- whisperx 의존성 문제로 임시로 주석 처리한 것으로 보임

---

## 🔄 현재 흐름 분석

### 정상 작동 시 예상 흐름:
```
1. 사용자가 "Whisper 전사" 버튼 클릭
   ↓
2. audio_detail.html의 form이 POST 요청 전송
   action="{% url 'transcribe_single_audio' audio.id %}"
   ↓
3. views.py의 transcribe_single_audio() 뷰 실행
   - audio.status = 'processing'으로 변경
   - transcribe_audio_task(audio.id) 호출 ← ❌ 여기서 NameError 발생
   ↓
4. tasks.py의 transcribe_audio_task() 실행
   - whisper_utils.transcribe_audio() 호출
   ↓
5. whisper_utils.py의 transcribe_audio() 실행
   - Whisper 모델로 실제 전사 수행
   - result['text'] 반환
   ↓
6. tasks.py에서 결과 저장
   - audio.transcription = result
   - audio.status = 'completed'
   ↓
7. audio_detail 페이지로 리다이렉트
   - 전사 내용이 화면에 표시됨
```

### 현재 실제 흐름:
```
1. 사용자가 "Whisper 전사" 버튼 클릭
   ↓
2. audio_detail.html의 form이 POST 요청 전송
   ↓
3. views.py의 transcribe_single_audio() 실행 시작
   ↓
4. ❌ transcribe_audio_task(audio.id) 호출 시 NameError 발생
   - NameError: name 'transcribe_audio_task' is not defined
   ↓
5. except 블록에서 처리:
   - audio.status = 'failed'
   - messages.error(request, '전사 중 오류가 발생했습니다: ...')
   ↓
6. audio_detail 페이지로 리다이렉트
   - 전사 실패 메시지 표시
   - 전사 내용은 비어있음
```

---

## 📝 관련 코드 위치

### 1. 템플릿 (정상)
**파일:** `voice_app/templates/voice_app/audio_detail.html` Line 591
```html
<form method="POST" action="{% url 'transcribe_single_audio' audio.id %}" style="display: inline;" id="transcribeForm">
  {% csrf_token %}
  <button type="submit" class="btn btn-success" id="transcribeBtn">🧠 Whisper 전사</button>
</form>
```
✅ 템플릿 코드는 정상

### 2. URL 패턴 (정상)
**파일:** `voice_app/urls.py` Line 63
```python
path('transcribe/<int:audio_id>/', views.transcribe_single_audio, name='transcribe_single_audio'),
```
✅ URL 라우팅은 정상

### 3. 뷰 함수 (문제 있음)
**파일:** `voice_app/views.py` Line 1269-1287
```python
def transcribe_single_audio(request, audio_id):
    audio = get_object_or_404(AudioRecord, id=audio_id)

    if request.method == 'POST':
        audio.status = 'processing'
        audio.save()
        
        try:
            # ❌ 여기서 NameError 발생
            transcribe_audio_task(audio.id)  # import가 주석 처리되어 있음
            messages.success(request, 'Whisper 전사가 시작되었습니다. 잠시 후 결과를 확인해주세요.')
        except Exception as e:
            audio.status = 'failed'
            audio.save()
            messages.error(request, f'전사 중 오류가 발생했습니다: {str(e)}')
    
    return redirect('audio_detail', audio_id=audio_id)
```

### 4. Import 문 (문제의 원인)
**파일:** `voice_app/views.py` Line 47
```python
# ❌ 주석 처리되어 있음
# from .tasks import transcribe_audio_task  # whisperx 의존성 때문에 임시 주석
```

### 5. Task 함수 (정상)
**파일:** `voice_app/tasks.py` Line 6-29
```python
def transcribe_audio_task(audio_id):
    audio = None
    try:
        audio = AudioRecord.objects.get(id=audio_id)
        audio.status = 'processing'
        audio.save()

        result = transcribe_audio(audio.audio_file.path)
        if result:
            audio.transcription = result
            audio.status = 'completed'
        else:
            audio.status = 'failed'
        audio.save()
    except Exception as e:
        if audio:
            audio.status = 'failed'
            audio.save()
        print(f"[Error] Transcription failed for ID {audio_id}: {e}")
```
✅ Task 함수 자체는 정상

### 6. Whisper 유틸리티 (정상)
**파일:** `voice_app/whisper_utils.py` Line 55-78
```python
def transcribe_audio(audio_path):
    if not model:
        print("[Whisper Error] Model not loaded.")
        return None

    if not os.path.exists(audio_path):
        print(f"[Whisper Error] File does not exist: {audio_path}")
        return None

    try:
        start = time.time()
        result = model.transcribe(audio_path, fp16=False, temperature=0.0, language="ko")
        elapsed = time.time() - start
        print(f"[Whisper] Transcription completed in {elapsed:.2f} seconds.")
        return result['text']
    except Exception as e:
        print(f"[Whisper Error] Failed to transcribe {audio_path}: {e}")
        return None
```
✅ Whisper 함수는 정상

---

## 🔧 해결 방법

### 방법 1: Import 주석 해제 (권장)
**파일:** `voice_app/views.py` Line 47

**변경 전:**
```python
# from .tasks import transcribe_audio_task  # whisperx 의존성 때문에 임시 주석
```

**변경 후:**
```python
from .tasks import transcribe_audio_task
```

**장점:**
- 가장 간단한 해결 방법
- 기존 구조 유지

**단점:**
- whisperx 의존성 문제가 있다면 서버 시작 시 오류 발생 가능

---

### 방법 2: 동기 방식으로 직접 호출
**파일:** `voice_app/views.py` Line 1269-1287

**변경 전:**
```python
try:
    transcribe_audio_task(audio.id)
    messages.success(request, 'Whisper 전사가 시작되었습니다. 잠시 후 결과를 확인해주세요.')
except Exception as e:
    audio.status = 'failed'
    audio.save()
    messages.error(request, f'전사 중 오류가 발생했습니다: {str(e)}')
```

**변경 후:**
```python
try:
    from .whisper_utils import transcribe_audio
    result = transcribe_audio(audio.audio_file.path)
    
    if result:
        audio.transcription = result
        audio.status = 'completed'
        messages.success(request, 'Whisper 전사가 완료되었습니다.')
    else:
        audio.status = 'failed'
        messages.error(request, '전사에 실패했습니다.')
    audio.save()
except Exception as e:
    audio.status = 'failed'
    audio.save()
    messages.error(request, f'전사 중 오류가 발생했습니다: {str(e)}')
```

**장점:**
- Celery나 별도 Task 없이 바로 실행
- 의존성 문제 우회

**단점:**
- 동기 방식이라 전사 완료까지 페이지 대기
- 긴 오디오 파일의 경우 타임아웃 가능

---

## 🧪 테스트 방법

### 1. 현재 상태 확인
```bash
cd /var/www/html/dj_voice_manage
grep -n "from .tasks import transcribe_audio_task" voice_app/views.py
```

### 2. 해결 후 테스트
1. 서버 실행: `./run.sh`
2. 브라우저에서 오디오 상세 페이지 접속
3. "Whisper 전사" 버튼 클릭
4. 결과 확인:
   - 성공: 전사 내용이 "전사 내용" 섹션에 표시됨
   - 실패: 오류 메시지 표시

### 3. 로그 확인
```bash
# Django 서버 로그 확인
tail -f django_server.log

# Whisper 처리 로그 확인 (tasks.py의 print 문)
# 성공 시: "[Whisper] Transcription completed in X.XX seconds."
# 실패 시: "[Error] Transcription failed for ID X: ..."
```

---

## 📊 현재 상태 요약

| 구성 요소 | 상태 | 비고 |
|---------|------|------|
| 템플릿 (audio_detail.html) | ✅ 정상 | Form과 버튼 정상 작동 |
| URL 패턴 | ✅ 정상 | 라우팅 설정 올바름 |
| 뷰 함수 | ⚠️ 문제 | import 주석으로 NameError 발생 |
| Tasks 모듈 | ✅ 정상 | 함수 구현 정상 |
| Whisper Utils | ✅ 정상 | Whisper 모델 로드 및 전사 기능 정상 |

**결론:** Import 주석 해제만으로 해결 가능

---

## 💡 권장 조치

1. **즉시 조치 (우선순위 높음):**
   ```python
   # voice_app/views.py Line 47
   from .tasks import transcribe_audio_task  # 주석 해제
   ```

2. **의존성 문제가 있다면:**
   - whisperx 라이브러리 재설치: `pip install whisperx`
   - 또는 방법 2 (동기 방식)로 변경

3. **테스트:**
   - 서버 재시작 후 Whisper 전사 기능 테스트
   - 로그 확인하여 정상 작동 검증

---

## 📌 참고사항

- Whisper 모델은 전역에서 로드되어 있음 (whisper_utils.py Line 11-18)
- 현재 'base' 모델 사용 중 (한국어 지원)
- GPU 사용 가능 시 자동으로 GPU 활용
- 전사 시간은 오디오 길이에 따라 다름 (평균 실시간의 0.1~0.3배)
