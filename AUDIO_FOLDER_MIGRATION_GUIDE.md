# 오디오 파일 폴더 구조 마이그레이션 가이드

## 📋 개요

오디오 파일 저장 구조를 **identifier 기반 폴더 구조**로 변경합니다.

### 기존 구조
```
media/audio/
├── child/
│   ├── abc123.wav
│   ├── abc123.json
│   ├── def456.wav
│   └── def456.json
├── senior/
│   ├── ghi789.wav
│   └── ghi789.json
└── auditory/
    ├── jkl012.wav
    └── jkl012.json
```

### 새로운 구조
```
media/audio/
├── child/
│   ├── C12345/
│   │   ├── abc123.wav
│   │   └── abc123.json
│   └── C67890/
│       ├── def456.wav
│       └── def456.json
├── senior/
│   ├── S12345/
│   │   ├── ghi789.wav
│   │   └── ghi789.json
│   └── S67890/
│       └── xyz999.wav
└── auditory/
    └── A12345/
        ├── jkl012.wav
        └── jkl012.json
```

## 🔧 변경 사항

### 1. models.py
`category_upload_path` 함수가 identifier를 포함한 경로를 생성합니다.

```python
def category_upload_path(instance, filename):
    """카테고리와 identifier별로 파일 저장 경로를 결정하는 함수
    
    저장 구조: audio/{category}/{identifier}/{filename}
    """
    category = instance.category or 'normal'
    
    if instance.identifier:
        return f'audio/{category}/{instance.identifier}/{filename}'
    else:
        return f'audio/{category}/{filename}'
```

### 2. views.py
파일 업로드 시 identifier 폴더를 자동 생성합니다.

```python
# identifier 기반 저장 경로 생성
if identifier:
    category_folder = os.path.join('audio', category, identifier)
else:
    category_folder = os.path.join('audio', category)
```

### 3. 데이터베이스
기존 `audio_file` 필드의 경로가 자동으로 업데이트됩니다.

- 기존: `audio/child/abc123.wav`
- 변경: `audio/child/C12345/abc123.wav`

## 🚀 마이그레이션 실행

### 1단계: 테스트 실행 (Dry-run)

실제 변경 없이 어떤 파일들이 이동될지 확인합니다.

```bash
cd /var/www/html/dj_voice_manage
python migrate_audio_files_to_identifier_folders.py --dry-run
```

### 2단계: 실제 마이그레이션

```bash
python migrate_audio_files_to_identifier_folders.py
```

### 3단계: 빈 디렉토리 정리 (선택사항)

마이그레이션 후 비어있는 카테고리 디렉토리를 정리합니다.

```bash
python migrate_audio_files_to_identifier_folders.py --cleanup
```

### 전체 실행 (마이그레이션 + 정리)

```bash
python migrate_audio_files_to_identifier_folders.py --cleanup
```

## ⚠️ 주의사항

### 1. 백업 필수
마이그레이션 전에 반드시 백업을 수행하세요.

```bash
# 데이터베이스 백업
cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d_%H%M%S)

# 미디어 파일 백업
tar -czf media_backup_$(date +%Y%m%d_%H%M%S).tar.gz media/
```

### 2. 서버 중지
마이그레이션 중에는 Django 서버를 중지하는 것이 좋습니다.

```bash
pkill -f "manage.py runserver"
```

### 3. identifier가 없는 파일
identifier가 없는 파일은 기존 구조를 유지합니다.

```
audio/child/no_identifier.wav  # identifier 없음, 이동하지 않음
```

### 4. 마이그레이션 실패 시
스크립트는 각 파일을 개별적으로 처리하므로, 일부 파일에서 오류가 발생해도 다른 파일은 계속 처리됩니다.

## 📊 마이그레이션 통계

스크립트 실행 후 다음과 같은 통계가 표시됩니다:

```
================================================================================
마이그레이션 완료
================================================================================
📊 통계:
   - 전체 레코드: 150
   - 마이그레이션: 145
   - 스킵: 3
   - 오류: 2
```

## 🔍 마이그레이션 후 확인

### 1. 폴더 구조 확인

```bash
tree -L 3 media/audio/
```

### 2. 데이터베이스 확인

```bash
sqlite3 db.sqlite3 "SELECT id, identifier, category, audio_file FROM voice_app_audiorecord LIMIT 10;"
```

### 3. 파일 접근 테스트

Django 서버를 재시작하고 오디오 파일 재생을 테스트합니다.

```bash
nohup python manage.py runserver 0.0.0.0:8010 > django_server.log 2>&1 &
```

## 🔄 롤백 (필요시)

마이그레이션에 문제가 있는 경우 백업으로 복원합니다.

```bash
# 데이터베이스 복원
cp db.sqlite3.backup_YYYYMMDD_HHMMSS db.sqlite3

# 미디어 파일 복원
rm -rf media/
tar -xzf media_backup_YYYYMMDD_HHMMSS.tar.gz
```

## 📝 새 파일 업로드

마이그레이션 후 새로 업로드되는 파일은 자동으로 새 구조에 저장됩니다.

### React Native 앱에서 업로드 시
- identifier가 포함된 경우: `audio/{category}/{identifier}/` 폴더에 저장
- identifier가 없는 경우: `audio/{category}/` 폴더에 저장

### Django 관리자에서 업로드 시
- AudioRecord 모델의 `identifier` 필드를 먼저 입력
- 파일을 업로드하면 자동으로 해당 identifier 폴더에 저장됨

## 🐛 문제 해결

### 파일을 찾을 수 없음 오류

```
⚠️ 파일 없음: /var/www/html/dj_voice_manage/media/audio/child/abc123.wav
```

**원인**: 파일이 이미 삭제되었거나 경로가 잘못됨  
**해결**: 해당 레코드를 수동으로 확인하고 필요시 삭제

### 권한 오류

```
❌ Permission denied: /var/www/html/dj_voice_manage/media/audio/child/C12345/
```

**원인**: 디렉토리 생성 권한 없음  
**해결**: 
```bash
chmod -R 755 media/
chown -R tyoon:tyoon media/
```

### 이미 올바른 위치

```
✓ 이미 올바른 위치: C12345 - abc123.wav
```

**원인**: 파일이 이미 마이그레이션 완료됨  
**해결**: 정상 상태, 추가 작업 불필요

## 📞 지원

문제가 발생하면 다음 로그를 확인하세요:

1. 마이그레이션 스크립트 출력
2. Django 서버 로그: `django_server.log`
3. 데이터베이스 상태: `sqlite3 db.sqlite3`

## ✅ 체크리스트

- [ ] 백업 완료 (데이터베이스 + 미디어 파일)
- [ ] Django 서버 중지
- [ ] Dry-run 테스트 실행
- [ ] 실제 마이그레이션 실행
- [ ] 마이그레이션 결과 확인
- [ ] Django 서버 재시작
- [ ] 파일 접근 테스트
- [ ] React Native 앱 테스트 (선택사항)
