# 오디오 파일 폴더 구조 변경 완료 보고서

## 📌 작업 요약

업로드된 오디오 파일의 저장 구조를 **identifier 기반 폴더 구조**로 변경했습니다.

### 변경 전 → 변경 후

```
변경 전:
audio/
  ├── child/
  │   ├── abc123.wav
  │   └── def456.wav
  └── senior/
      └── ghi789.wav

변경 후:
audio/
  ├── child/
  │   ├── C12345/
  │   │   ├── abc123.wav
  │   │   └── abc123.json
  │   └── C67890/
  │       └── def456.wav
  └── senior/
      └── S12345/
          └── ghi789.wav
```

## 🔧 수정된 파일

### 1. `/voice_app/models.py`

**수정 내용**: `category_upload_path` 함수를 identifier 기반으로 변경

```python
def category_upload_path(instance, filename):
    """카테고리와 identifier별로 파일 저장 경로를 결정하는 함수
    
    저장 구조: audio/{category}/{identifier}/{filename}
    예: audio/child/C12345/audio.wav
    
    identifier가 없는 경우: audio/{category}/{filename}
    """
    category = instance.category or 'normal'
    
    # identifier가 있으면 identifier 폴더 생성
    if instance.identifier:
        return f'audio/{category}/{instance.identifier}/{filename}'
    else:
        # identifier가 없으면 기존 방식대로 (하위 호환성)
        return f'audio/{category}/{filename}'
```

**영향**:
- 새로 업로드되는 모든 파일이 자동으로 identifier 폴더에 저장됨
- identifier가 없는 파일은 기존 방식대로 저장 (하위 호환성 유지)

### 2. `/voice_app/views.py`

**수정 위치**: `upload_audio` 함수 (라인 667-677)

**수정 내용**: 파일 저장 시 identifier 폴더 자동 생성

```python
# identifier 기반 저장 경로 생성
# 구조: audio/{category}/{identifier}/{filename}
if identifier:
    category_folder = os.path.join('audio', category, identifier)
else:
    # identifier가 없으면 기존 방식 (하위 호환성)
    category_folder = os.path.join('audio', category)

m4a_storage_path = os.path.join(category_folder, m4a_filename)

# 카테고리(+identifier) 폴더가 없으면 생성
category_media_folder = os.path.join(settings.MEDIA_ROOT, category_folder)
os.makedirs(category_media_folder, exist_ok=True)

print(f"[DEBUG] Storage path: {m4a_storage_path}")
if identifier:
    print(f"[DEBUG] Using identifier-based folder: {identifier}")
```

**영향**:
- React Native 앱에서 업로드 시 identifier가 있으면 자동으로 해당 폴더에 저장
- JSON 메타데이터 파일도 같은 폴더에 저장됨

### 3. 새 파일 생성

#### `migrate_audio_files_to_identifier_folders.py`
- **목적**: 기존 파일들을 새 구조로 마이그레이션
- **기능**:
  - identifier가 있는 모든 AudioRecord 조회
  - 각 파일을 `audio/{category}/{identifier}/` 폴더로 이동
  - 데이터베이스의 `audio_file` 경로 자동 업데이트
  - JSON 메타데이터도 함께 이동
  - Dry-run 모드 지원
  - 통계 및 에러 리포트

#### `run_migration_with_backup.sh`
- **목적**: 백업과 마이그레이션을 자동화
- **기능**:
  - 데이터베이스 자동 백업
  - 미디어 파일 자동 백업 (tar.gz)
  - Django 서버 중지/재시작
  - 마이그레이션 실행
  - 결과 확인

#### `AUDIO_FOLDER_MIGRATION_GUIDE.md`
- **목적**: 상세한 마이그레이션 가이드 제공
- **내용**: 
  - 단계별 실행 방법
  - 주의사항
  - 문제 해결 가이드
  - 체크리스트

## 📊 현재 상태

### 데이터베이스 통계
```
총 AudioRecord: ~4,228개 (identifier 있음)
마이그레이션 필요: ~4,228개 파일
```

### Dry-run 테스트 결과
```bash
$ python migrate_audio_files_to_identifier_folders.py --dry-run

================================================================================
오디오 파일 마이그레이션 시작
모드: DRY-RUN (실제 변경 없음)
================================================================================

📊 identifier가 있는 레코드 수: 4228

🔄 [1/4228] S43518
   현재: audio/senior/516e037450ef4c1492fc689dba300339.wav
   새 위치: audio/senior/S43518/516e037450ef4c1492fc689dba300339.wav
   [DRY-RUN] 실제 실행 시 마이그레이션됨
...
```

## 🚀 마이그레이션 실행 방법

### 방법 1: 자동 백업 스크립트 사용 (권장)

```bash
cd /var/www/html/dj_voice_manage
./run_migration_with_backup.sh
```

이 스크립트는 자동으로:
1. ✅ 데이터베이스 백업
2. ✅ 미디어 파일 백업
3. ✅ Django 서버 중지
4. ✅ 마이그레이션 실행
5. ✅ Django 서버 재시작

### 방법 2: 수동 실행

```bash
# 1. 백업
cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d_%H%M%S)
tar -czf media_backup_$(date +%Y%m%d_%H%M%S).tar.gz media/

# 2. 서버 중지
pkill -f "manage.py runserver"

# 3. 마이그레이션
python migrate_audio_files_to_identifier_folders.py

# 4. 서버 재시작
nohup python manage.py runserver 0.0.0.0:8010 > django_server.log 2>&1 &
```

## ⚠️ 중요 사항

### 1. 백업은 필수
마이그레이션 전 반드시 백업을 생성하세요.

### 2. 하위 호환성
- identifier가 없는 파일은 기존 구조 유지
- 기존 코드와의 호환성 보장

### 3. 점진적 마이그레이션
- 새 파일: 자동으로 새 구조에 저장
- 기존 파일: 마이그레이션 스크립트로 이동

### 4. 파일 접근
- Django의 FileField가 자동으로 올바른 경로 관리
- URL 접근도 자동으로 처리됨

## 🔍 마이그레이션 후 확인 사항

### 1. 폴더 구조 확인
```bash
tree -L 3 media/audio/ | head -30
```

### 2. 데이터베이스 확인
```bash
sqlite3 db.sqlite3 "SELECT id, identifier, category, audio_file FROM voice_app_audiorecord WHERE identifier IS NOT NULL LIMIT 5;"
```

### 3. 웹 인터페이스 테스트
- 오디오 목록 페이지 접속
- 오디오 상세 페이지 접속
- 파일 재생 테스트
- 다운로드 테스트

### 4. React Native 앱 테스트
- 새 파일 업로드
- 업로드된 파일 재생
- identifier 폴더 생성 확인

## 📈 예상 효과

### 장점
1. **조직화**: identifier별로 파일이 그룹화되어 관리가 용이
2. **확장성**: 향후 identifier별 추가 파일 저장 가능
3. **성능**: 카테고리 폴더의 파일 수 감소
4. **추적성**: identifier로 파일 그룹 쉽게 파악

### 저장 공간
- 추가 공간 사용: 없음 (파일 이동만 수행)
- 디렉토리 메타데이터: 약간 증가 (무시할 수준)

## 🔧 문제 해결

### 마이그레이션 실패 시
```bash
# 백업에서 복원
cp backups/db.sqlite3.backup_YYYYMMDD_HHMMSS db.sqlite3
tar -xzf backups/media_backup_YYYYMMDD_HHMMSS.tar.gz
```

### 특정 파일만 재마이그레이션
```python
# Django shell에서
python manage.py shell

from voice_app.models import AudioRecord
import shutil
from pathlib import Path

# 특정 레코드 가져오기
record = AudioRecord.objects.get(id=123)

# 수동 이동 (예시)
# ... 파일 이동 로직 ...
```

## 📞 추가 지원

자세한 내용은 다음 문서를 참조하세요:
- `AUDIO_FOLDER_MIGRATION_GUIDE.md`: 상세 가이드
- `migrate_audio_files_to_identifier_folders.py`: 스크립트 소스코드

---

**작성일**: 2025-11-27  
**작성자**: GitHub Copilot  
**상태**: ✅ 코드 변경 완료, 마이그레이션 대기
