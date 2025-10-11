# 오디오 파일 재업로드 기능 가이드

## 📋 개요

보안을 고려한 오디오 파일 다운로드 및 재업로드 기능입니다. 원본 파일을 다운로드한 후, 편집하여 동일한 이름으로 다시 업로드할 수 있습니다.

## 🔐 보안 기능

### 1. 파일명 검증
- **정확한 파일명 일치 필수**: 업로드된 파일명이 원본과 정확히 일치해야 합니다
- 대소문자 구분 없음 (자동으로 소문자 변환하여 비교)
- 경로는 무시하고 파일명만 비교

### 2. 오디오 파일 검증
```python
# 지원 포맷
- WAV (audio/wav, audio/wave, audio/x-wav)
- MP3 (audio/mpeg, audio/mp3)
- OGG (audio/ogg)
- FLAC (audio/flac, audio/x-flac)
- AAC (audio/aac)
- M4A (audio/m4a)

# 파일 제약
- 최대 크기: 100MB
- 최소 길이: 0.1초
- 최대 길이: 10분 (600초)
```

### 3. 실제 오디오 내용 검증
- **pydub + AudioSegment**: 파일이 실제로 재생 가능한 오디오인지 확인
- MIME 타입만으로는 부족 (악의적인 파일 차단)
- 오디오 속성 추출: duration, sample_rate, channels

### 4. 권한 제한
- **Staff 또는 Superuser만** 파일 교체 가능
- `@login_required` 데코레이터로 로그인 필수

### 5. 원본 파일 백업
- 교체 전 자동으로 원본 파일 백업
- 백업 위치: `media/audio_backups/`
- 백업 파일명: `{원본파일명}_backup_{타임스탬프}.wav`
- 예시: `audio123_backup_20251011_162530.wav`

### 6. 변경 이력 기록
- 모든 파일 교체 내역을 `category_specific_data` JSON 필드에 저장
```json
{
  "file_history": [
    {
      "timestamp": "2025-10-11T16:25:30.123456",
      "user": "admin",
      "action": "replace",
      "old_hash": "abc123...",
      "new_hash": "def456...",
      "backup_path": "/media/audio_backups/audio123_backup_20251011_162530.wav",
      "validation": {
        "format": "wav",
        "duration": 3.5,
        "sample_rate": 16000,
        "channels": 1
      }
    }
  ]
}
```

### 7. 파일 해시 검증
- SHA256 해시로 파일 무결성 확인
- 이전 파일과 새 파일의 해시 비교 가능
- 변경 이력에 해시 저장

## 🎯 사용 방법

### 1. 오디오 파일 다운로드

**방법 A: 상세 페이지에서 다운로드**
```
1. /voice/audio/{audio_id}/ 접속
2. "💾 다운로드" 버튼 클릭
3. 파일이 원본 파일명으로 다운로드됨
```

**방법 B: 직접 URL 호출**
```
GET /voice/audio/{audio_id}/download/
```

### 2. 오디오 파일 편집
- 다운로드한 파일을 오디오 편집 프로그램에서 편집
- **중요**: 파일명을 변경하지 말 것!
- 포맷 변경 가능 (WAV → MP3 등), 단 원본 파일명 확장자와 일치해야 함

### 3. 재업로드

**방법 A: UI 사용 (staff/superuser만)**
```
1. /voice/audio/{audio_id}/ 접속
2. "🔄 파일 재업로드" 버튼 클릭
3. 모달창에서 파일 선택
4. 자동 검증 후 "🔄 업로드" 버튼 활성화
5. 업로드 진행률 표시
6. 성공 시 페이지 자동 새로고침
```

**방법 B: API 호출**
```bash
curl -X POST \
  -H "X-CSRFToken: {csrf_token}" \
  -F "audio_file=@/path/to/audio.wav" \
  http://your-domain/voice/audio/{audio_id}/reupload/
```

**응답 (성공)**
```json
{
  "success": true,
  "message": "파일이 성공적으로 교체되었습니다",
  "backup_path": "/media/audio_backups/audio123_backup_20251011_162530.wav",
  "old_hash": "abc123def456...",
  "new_hash": "789ghi012jkl...",
  "validation": {
    "valid": true,
    "format": "wav",
    "duration": 3.5,
    "sample_rate": 16000,
    "channels": 1
  }
}
```

**응답 (실패)**
```json
{
  "success": false,
  "error": "파일명이 일치하지 않습니다 (원본: audio.wav, 업로드: edited_audio.wav)",
  "validation": {}
}
```

## 🛡️ 보안 규칙 요약

| 규칙 | 설명 | 차단 예시 |
|------|------|-----------|
| 파일명 일치 | 원본과 정확히 동일한 파일명 | `audio.wav` → `edited_audio.wav` ❌ |
| 실제 오디오 | pydub으로 로드 가능한 파일 | 텍스트 파일에 `.wav` 확장자 ❌ |
| 권한 확인 | staff 또는 superuser만 | 일반 사용자 ❌ |
| 크기 제한 | 최대 100MB | 150MB 파일 ❌ |
| 길이 제한 | 0.1초 ~ 10분 | 15분짜리 파일 ❌ |
| 포맷 제한 | WAV/MP3/OGG/FLAC/AAC/M4A만 | `.txt` 파일 ❌ |

## 📁 파일 구조

```
voice_app/
├── audio_reupload.py          # 재업로드 유틸리티 모듈
│   ├── validate_audio_file()  # 오디오 파일 검증
│   ├── verify_filename_match() # 파일명 일치 확인
│   ├── calculate_file_hash()  # SHA256 해시 계산
│   ├── backup_original_file() # 원본 백업
│   └── replace_audio_file()   # 파일 교체 (메인 함수)
├── views.py
│   ├── audio_download()       # 파일 다운로드 뷰
│   └── audio_reupload()       # 파일 재업로드 뷰
├── urls.py
│   ├── /audio/<id>/download/  # 다운로드 URL
│   └── /audio/<id>/reupload/  # 재업로드 URL
└── templates/voice_app/
    └── audio_detail.html      # 재업로드 UI + 모달
```

## 🔧 의존성

```python
# 필수 패키지
pip install pydub

# 시스템 요구사항
apt-get install ffmpeg  # pydub 백엔드
```

## 🎨 UI 요소

### 다운로드 버튼
```html
<a href="{% url 'audio_download' audio.id %}" class="btn btn-primary">
  💾 다운로드
</a>
```

### 재업로드 버튼 (staff만 표시)
```html
{% if user.is_staff or user.is_superuser %}
<button type="button" class="btn btn-warning" onclick="openReuploadModal()">
  🔄 파일 재업로드
</button>
{% endif %}
```

### 재업로드 모달
- 실시간 파일명 검증 (JavaScript)
- 파일 크기 및 타입 체크
- 업로드 진행률 표시 (XMLHttpRequest)
- 보안 규칙 안내

## 📊 데이터베이스 변경사항

### AudioRecord 모델
```python
# 기존 필드 활용 (변경 없음)
- audio_file: FileField  # 실제 오디오 파일
- duration: FloatField   # 자동 업데이트
- category_specific_data: JSONField  # file_history 추가

# 새로 추가되는 JSON 구조
category_specific_data = {
    # ... 기존 데이터 ...
    "file_history": [  # 새로 추가
        {
            "timestamp": "ISO 8601 형식",
            "user": "사용자명",
            "action": "replace",
            "old_hash": "SHA256 해시",
            "new_hash": "SHA256 해시",
            "backup_path": "백업 파일 경로",
            "validation": {
                "format": "파일 포맷",
                "duration": 3.5,
                "sample_rate": 16000,
                "channels": 1
            }
        }
    ]
}
```

## ⚠️ 주의사항

1. **백업 디렉토리 권한**: `media/audio_backups/` 디렉토리에 쓰기 권한 필요
2. **디스크 공간**: 백업 파일이 누적되므로 주기적으로 정리 필요
3. **동시 업로드**: 동일한 파일에 대한 동시 재업로드는 지원하지 않음
4. **파일명 변경 불가**: 원본 파일명 그대로 유지해야 함
5. **권한 관리**: staff 권한을 신중하게 부여

## 🧪 테스트 시나리오

### 정상 케이스
```python
# 1. 정상적인 재업로드
원본: audio123.wav (16kHz, 3.5초)
편집: audio123.wav (16kHz, 3.2초, 노이즈 제거)
결과: ✅ 성공

# 2. 포맷 변환 (파일명 일치)
원본: audio123.wav
편집: audio123.wav (MP3로 변환 후 WAV로 재저장)
결과: ✅ 성공
```

### 보안 차단 케이스
```python
# 1. 파일명 불일치
원본: audio123.wav
업로드: audio123_edited.wav
결과: ❌ 차단 (파일명 불일치)

# 2. 비오디오 파일
원본: audio123.wav
업로드: malicious.exe를 audio123.wav로 이름 변경
결과: ❌ 차단 (pydub 검증 실패)

# 3. 권한 부족
사용자: 일반 회원
결과: ❌ 차단 (staff 아님)

# 4. 파일 크기 초과
원본: audio123.wav (5MB)
업로드: audio123.wav (120MB)
결과: ❌ 차단 (100MB 초과)
```

## 📈 향후 개선 가능 사항

1. **버전 관리**: 백업 파일 목록 UI에서 관리
2. **자동 정리**: 오래된 백업 파일 자동 삭제 (30일 이상)
3. **비교 기능**: 원본과 새 파일의 파형 비교
4. **일괄 재업로드**: 여러 파일 동시 재업로드
5. **롤백 기능**: 백업에서 원본 복원
6. **변경 이력 UI**: 파일 변경 이력 시각화

## 🔗 관련 URL

- 오디오 목록: `/voice/audio_list/`
- 오디오 상세: `/voice/audio/{audio_id}/`
- 다운로드: `/voice/audio/{audio_id}/download/`
- 재업로드: `/voice/audio/{audio_id}/reupload/`
- 대시보드: `/voice/dashboard/`

## 💡 사용 예시

```python
# 1. 특정 오디오 파일 다운로드
GET /voice/audio/123/download/

# 2. 편집 후 재업로드
POST /voice/audio/123/reupload/
Content-Type: multipart/form-data

audio_file: (binary data)

# 3. 변경 이력 확인
audio = AudioRecord.objects.get(id=123)
history = audio.category_specific_data.get('file_history', [])
for entry in history:
    print(f"{entry['timestamp']}: {entry['user']} - {entry['action']}")
```
