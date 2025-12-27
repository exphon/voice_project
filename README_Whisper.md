# README_Whisper.md

이 문서는 이 프로젝트에서 **Whisper / WhisperX 전사(ASR)** 파이프라인을 어떻게 구성/운영하는지, 그리고 최근 반영된 주요 변경사항(모델 `large-v3`, 한국어 강제, 혼합 발화(유아+성인) 대응)을 정리합니다.

---

## 1) 목표

- **모델 고정**: Whisper/WhisperX 전사를 `large-v3`로 통일
- **언어 강제**: 전사 결과가 가능한 한 **반드시 한국어(ko)** 로 나오도록 강제
- **혼합 발화 개선**: `5살 이하 + 성인`이 같은 WAV에 섞인 경우에도
  - 무음/긴 침묵을 제거하고
  - 짧은 단어/빠른 연속 발화/문장·문단 발화를 안정적으로 처리
  - 가능하면 **화자 분리(diarization)** 로 `[아동] ... / [선생님] ...` 형태로 합치기

---

## 2) 핵심 변경 요약 (2025-12-25 기준)

### 2.1 Whisper (openai-whisper)

- 기본 모델을 `large-v3`로 로딩
- `language='ko'`, `task='transcribe'`, 한국어 `initial_prompt`를 기본 적용
- 결과 텍스트가 한국어로 보이지 않을 때(한글 비율이 낮을 때) **1회 재시도**

적용 파일:
- `voice_app/whisper_utils.py`
- (레거시) `voice_app/views_3.py`
- (관리 커맨드) `voice_app/management/commands/transcribe_all.py`

### 2.2 WhisperX

- 프로젝트 설정 `WHISPERX_CONFIG`에서
  - `MODEL_SIZE='large-v3'`
  - `FORCE_LANGUAGE='ko'` (요청 파라미터보다 강함)
  - `LANGUAGE='ko'`, `TASK='transcribe'`, `INITIAL_PROMPT` 기본값 추가
- WhisperX 버전에 따라 `task/beam_size/initial_prompt/language` 옵션이 지원되지 않을 수 있어
  - `TypeError` 발생 시 **지원되지 않는 키를 제거하고 재시도**하는 안전 장치 추가

적용 파일:
- `voice_project/settings.py`
- `utils/django_whisperx_service.py`

### 2.3 혼합 발화(5살 이하 + 성인) 대응: VAD + diarization

- **VAD 기반 구간 분리(의존성 최소화)**
  - ffmpeg로 16kHz mono WAV로 변환 후
  - 에너지(RMS→dBFS) 기반으로 발화 구간만 추출
  - 긴 구간은 20초 단위로 잘라(약간 overlap) 구간별 전사 후 합침
- **pyannote diarization 기반 화자별 전사(가능할 때만)**
  - pyannote로 화자 구간을 얻고
  - (기본 정책) 발화량이 많은 화자를 `아동`, 다음을 `선생님`으로 라벨링
  - 각 화자 구간을 다시 VAD로 잘게 나눈 뒤 전사하여
  - 결과를 시간 순서로 `[아동] ...` / `[선생님] ...` 형태로 합침
- diarization이 설치/토큰 설정이 안 되어 실패하면 자동으로 **VAD-only로 폴백**

적용 파일:
- `voice_app/whisper_utils.py`
- 호출/저장 연결: `voice_app/tasks.py`, `voice_app/views.py`

---

## 3) 설정 (WhisperX)

설정 위치: `voice_project/settings.py` 의 `WHISPERX_CONFIG`

현재 값(요약):
- `MODEL_SIZE = 'large-v3'`
- `LANGUAGE = 'ko'`
- `FORCE_LANGUAGE = 'ko'`  ← 요청으로 다른 언어가 들어와도 무시하고 한국어 고정
- `TASK = 'transcribe'`
- `INITIAL_PROMPT = '다음은 한국어 음성의 전사입니다. ... 반드시 한국어로만 전사하세요.'`
- `TEMPERATURE = 0.0`
- `BEAM_SIZE = 5`

> 참고: `WHISPERX_CONFIG`는 WhisperX 서비스(`utils/django_whisperx_service.py`)에서 직접 사용됩니다.

---

## 4) 실제 전사 실행 경로(중요)

이 프로젝트에는 전사가 여러 경로로 호출될 수 있습니다.

### 4.1 기본(일반) 전사

- 핵심 유틸: `voice_app/whisper_utils.py` 의 `transcribe_audio(audio_path)`
- 사용하는 모델: Whisper `large-v3`
- 기본 강제 옵션:
  - `language='ko'`
  - `task='transcribe'`
  - `initial_prompt=한국어 전사 유도 문구`
  - `temperature=0.0`

### 4.2 5살 이하 + 성인 혼합 발화 전사

- 엔트리포인트: `voice_app/whisper_utils.py` 의
  - `transcribe_audio_mixed_child_adult(audio_path, prefer_diarization=True, ...)`

동작 우선순위:
1) diarization 가능 → `mode='diarization'` 로 `[화자] 텍스트` 형식
2) diarization 불가/실패 → `mode='vad'` 로 VAD-only 합쳐진 텍스트

### 4.3 자동 적용 위치(어떤 오디오에 혼합 발화 파이프라인을 쓰는가)

- `voice_app/tasks.py` 의 `transcribe_audio_task(audio_id)`에서 자동 판별
  - `age_in_months <= 60` 또는 `age <= 5`이면 혼합 파이프라인 사용
  - `category == 'child'`인데 나이 정보가 누락된 경우도 혼합 파이프라인 사용
- `voice_app/views.py` 의 `transcribe_unprocessed`에서도 동일 정책 적용

> 목적: 업로드된 아동 음성에 성인(보호자/교사) 발화가 섞인 경우가 많아서,
> 기본 전사보다 VAD/diarization을 우선 적용해 정확도를 개선합니다.

---

## 5) VAD 세부(무음/구간 분리)

구현 위치: `voice_app/whisper_utils.py`

### 5.1 알고리즘(간단)

- ffmpeg로 입력을 `16kHz / mono / pcm_s16le`로 변환
- 30ms 프레임 단위로 RMS를 구하고 dBFS 유사값으로 변환
- 임계값 이상이면 speech로 간주
- speech 구간 사이 gap을 병합/패딩 처리
- 긴 구간은 `max_segment_s`(기본 20s)로 자르고 overlap을 조금 둬서 문장 단절을 줄임

### 5.2 조절 파라미터

- `threshold_dbfs` (기본 -35.0): 높일수록(예: -30) 더 공격적으로 무음을 제거
- `frame_ms` (기본 30): 낮추면 더 민감하지만 변동 가능
- `min_speech_ms` (기본 250): 너무 짧은 소리(클릭/잡음)를 제거
- `padding_ms` (기본 200): 단어 앞뒤가 잘리는 것을 줄임
- `max_segment_s` (기본 20): 긴 발화를 조각으로 나누는 최대 길이

---

## 6) diarization 세부(화자 분리)

### 6.1 의존성/토큰

- diarization은 `pyannote.audio` 기반입니다.
- HuggingFace 모델 접근을 위해 환경변수 `HUGGINGFACE_TOKEN`이 필요합니다.
- 안내 문서: `SPEAKER_DIARIZATION_GUIDE.md`

### 6.2 동작

- `voice_app/diarization_utils.py` 의 `SpeakerDiarizer.perform_diarization()` 사용
- 기본: 1~2명 화자(`min_speakers=1`, `max_speakers=2`)를 가정
- 라벨 자동 할당:
  - 발화량이 더 많은 화자를 `아동`
  - 그 다음을 `선생님`
  - (주의) 현실에서는 성인이 더 많이 말할 수도 있으므로, 필요하면 라벨 규칙을 변경하세요.

### 6.3 전사 결합 포맷

- diarization 성공 시 결과는 아래처럼 줄바꿈 형태로 합쳐집니다:

```text
[아동] ...
[선생님] ...
[아동] ...
```

- diarization 실패/미설치 시 VAD-only 텍스트 하나로 반환됩니다.

---

## 7) 운영/사용 방법

### 7.1 관리 커맨드(일괄 전사)

```bash
python manage.py transcribe_all
```

- Whisper `large-v3`로 전사
- 한국어 강제 옵션 포함

### 7.2 웹(미전사 일괄 전사)

- `transcribe_unprocessed` 뷰는
  - 5살 이하/아동은 mixed 파이프라인(diarization/VAD)
  - 그 외는 기본 `transcribe_audio`

### 7.3 코드에서 직접 호출

```python
from voice_app.whisper_utils import (
    transcribe_audio,
    transcribe_audio_vad_segmented,
    transcribe_audio_mixed_child_adult,
)

text = transcribe_audio('/path/to/file.wav')
text_vad = transcribe_audio_vad_segmented('/path/to/file.wav')
out = transcribe_audio_mixed_child_adult('/path/to/file.wav', prefer_diarization=True)
print(out['mode'], out['text'])
```

---

## 8) 필수 시스템 의존성

### 8.1 ffmpeg

- VAD 구간 추출/포맷 변환/세그먼트 추출에 `ffmpeg`가 사용됩니다.

확인:
```bash
ffmpeg -version
```

### 8.2 GPU(선택)

- Whisper `large-v3`는 모델이 크므로 CPU에서도 동작하나 시간이 오래 걸릴 수 있습니다.
- GPU가 있으면 훨씬 빠릅니다.

---

## 9) 트러블슈팅

### 9.1 diarization이 자동으로 VAD-only로만 떨어짐

- pyannote 미설치 또는 HuggingFace 토큰 미설정일 가능성이 큽니다.
- 해결:
  - `export HUGGINGFACE_TOKEN=...`
  - 모델 접근 권한 승인
  - `SPEAKER_DIARIZATION_GUIDE.md` 참고

### 9.2 whisperx 옵션 키 에러(TypeError)

- whisperx 버전에 따라 `task`, `beam_size`, `initial_prompt` 지원이 다를 수 있습니다.
- 현재 구현은 자동으로 지원되지 않는 옵션을 제거하고 재시도하도록 되어 있습니다.

### 9.3 한국어가 아닌 텍스트가 섞여 나옴

- 기본적으로 `language='ko'` + 한국어 프롬프트를 넣고,
  결과가 한국어로 보이지 않으면 1회 재시도합니다.
- 그래도 영어/숫자/기호가 섞일 수 있습니다(특히 고유명사, 약어, 배경음).
- 더 강하게 강제하려면:
  - `INITIAL_PROMPT_KO` 문구를 더 엄격하게 수정
  - VAD 임계값(`threshold_dbfs`) 조정으로 잡음을 더 제거

---

## 10) 관련 파일 목록(변경/핵심)

- Whisper/WhisperX 모델/언어 강제 및 혼합 파이프라인
  - `voice_app/whisper_utils.py`
- 전사 실행(자동 분기, diarization_data 저장)
  - `voice_app/tasks.py`
  - `voice_app/views.py` (`transcribe_unprocessed`)
- WhisperX 서비스(설정 기반, 옵션 호환 재시도)
  - `utils/django_whisperx_service.py`
- 설정
  - `voice_project/settings.py`
- diarization 유틸
  - `voice_app/diarization_utils.py`
  - `SPEAKER_DIARIZATION_GUIDE.md`

---

## 11) 주의(성능/비용)

- `large-v3`는 정확도가 좋은 대신 **VRAM/RAM 사용량이 큽니다.**
- diarization(pyannote)은 추가 모델을 로드하므로 **처리 시간/메모리**가 증가합니다.
- 긴 오디오(수 분 이상)는:
  - VAD로 먼저 구간을 줄이고
  - diarization은 필요할 때만 켜는 것을 권장합니다.
