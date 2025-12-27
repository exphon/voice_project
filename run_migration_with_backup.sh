#!/bin/bash
# 백업 및 마이그레이션 자동화 스크립트

set -e  # 오류 발생 시 스크립트 중단

SCRIPT_DIR="/var/www/html/dj_voice_manage"
BACKUP_DIR="$SCRIPT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=========================================="
echo "오디오 파일 폴더 구조 마이그레이션"
echo "시작 시간: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo

# 백업 디렉토리 생성
mkdir -p "$BACKUP_DIR"

echo "1️⃣  백업 생성 중..."
echo "   - 데이터베이스: db.sqlite3"
cp "$SCRIPT_DIR/db.sqlite3" "$BACKUP_DIR/db.sqlite3.backup_$TIMESTAMP"
echo "   ✅ 데이터베이스 백업 완료"

echo "   - 미디어 파일: media/"
tar -czf "$BACKUP_DIR/media_backup_$TIMESTAMP.tar.gz" -C "$SCRIPT_DIR" media/ 2>/dev/null || true
echo "   ✅ 미디어 파일 백업 완료"
echo

echo "2️⃣  Django 서버 중지 중..."
pkill -f "manage.py runserver" 2>/dev/null || echo "   ⚠️  실행 중인 서버 없음"
sleep 2
echo "   ✅ 서버 중지 완료"
echo

echo "3️⃣  마이그레이션 실행 중..."
cd "$SCRIPT_DIR"
python migrate_audio_files_to_identifier_folders.py

echo
echo "4️⃣  Django 서버 재시작 중..."
nohup python manage.py runserver 0.0.0.0:8010 > django_server.log 2>&1 &
SERVER_PID=$!
echo "   ✅ 서버 시작됨 (PID: $SERVER_PID)"
sleep 3

# 서버가 정상적으로 시작되었는지 확인
if ps -p $SERVER_PID > /dev/null; then
    echo "   ✅ 서버가 정상적으로 실행 중입니다"
else
    echo "   ❌ 서버 시작 실패. 로그를 확인하세요: tail -f django_server.log"
    exit 1
fi

echo
echo "=========================================="
echo "마이그레이션 완료!"
echo "종료 시간: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo
echo "📂 백업 위치:"
echo "   - 데이터베이스: $BACKUP_DIR/db.sqlite3.backup_$TIMESTAMP"
echo "   - 미디어 파일: $BACKUP_DIR/media_backup_$TIMESTAMP.tar.gz"
echo
echo "🔍 다음 명령어로 서버 로그를 확인하세요:"
echo "   tail -f django_server.log"
echo
echo "✅ 웹 브라우저에서 오디오 파일 재생을 테스트하세요:"
echo "   http://210.125.93.241:8010/audio/"
