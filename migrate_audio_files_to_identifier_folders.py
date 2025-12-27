#!/usr/bin/env python
"""
오디오 파일을 identifier 기반 폴더 구조로 마이그레이션

기존 구조: audio/{category}/{filename}
새 구조: audio/{category}/{identifier}/{filename}

실행 방법:
python migrate_audio_files_to_identifier_folders.py --dry-run  # 테스트 실행
python migrate_audio_files_to_identifier_folders.py           # 실제 마이그레이션
"""

import os
import sys
import django
import shutil
from pathlib import Path
import argparse

# Django 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_project.settings')
django.setup()

from django.conf import settings
from voice_app.models import AudioRecord

def migrate_audio_files(dry_run=False):
    """오디오 파일들을 identifier 폴더 구조로 마이그레이션"""
    
    print("=" * 80)
    print("오디오 파일 마이그레이션 시작")
    print(f"모드: {'DRY-RUN (실제 변경 없음)' if dry_run else '실제 마이그레이션'}")
    print("=" * 80)
    print()
    
    media_root = Path(settings.MEDIA_ROOT)
    audio_dir = media_root / 'audio'
    
    if not audio_dir.exists():
        print(f"❌ 오디오 디렉토리를 찾을 수 없습니다: {audio_dir}")
        return
    
    # identifier가 있는 모든 AudioRecord 조회
    records_with_identifier = AudioRecord.objects.filter(
        identifier__isnull=False
    ).exclude(identifier='')
    
    total_count = records_with_identifier.count()
    print(f"📊 identifier가 있는 레코드 수: {total_count}")
    print()
    
    if total_count == 0:
        print("⚠️ identifier가 있는 레코드가 없습니다.")
        return
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    for idx, record in enumerate(records_with_identifier, 1):
        try:
            # 현재 파일 경로
            current_path = Path(record.audio_file.path)
            
            if not current_path.exists():
                print(f"⚠️  [{idx}/{total_count}] 파일 없음: {current_path}")
                skipped_count += 1
                continue
            
            # 현재 파일이 이미 identifier 폴더에 있는지 확인
            # 경로 구조: audio/{category}/{identifier}/{filename}
            path_parts = current_path.relative_to(media_root).parts
            
            # 이미 올바른 구조인지 확인
            if len(path_parts) >= 4 and path_parts[0] == 'audio' and path_parts[2] == record.identifier:
                print(f"✓ [{idx}/{total_count}] 이미 올바른 위치: {record.identifier} - {current_path.name}")
                skipped_count += 1
                continue
            
            # 새 경로 생성
            category = record.category or 'normal'
            identifier = record.identifier
            filename = current_path.name
            
            new_relative_path = f'audio/{category}/{identifier}/{filename}'
            new_path = media_root / new_relative_path
            
            print(f"🔄 [{idx}/{total_count}] {record.identifier}")
            print(f"   현재: {current_path.relative_to(media_root)}")
            print(f"   새 위치: {new_relative_path}")
            
            if not dry_run:
                # 새 디렉토리 생성
                new_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 파일 이동
                shutil.move(str(current_path), str(new_path))
                
                # 데이터베이스 업데이트
                record.audio_file.name = new_relative_path
                record.save(update_fields=['audio_file'])
                
                print(f"   ✅ 마이그레이션 완료")
                
                # JSON 메타데이터 파일도 함께 이동
                json_filename = current_path.stem + '.json'
                old_json_path = current_path.parent / json_filename
                if old_json_path.exists():
                    new_json_path = new_path.parent / json_filename
                    shutil.move(str(old_json_path), str(new_json_path))
                    print(f"   📄 JSON 메타데이터도 이동됨")
            else:
                print(f"   [DRY-RUN] 실제 실행 시 마이그레이션됨")
            
            migrated_count += 1
            print()
            
        except Exception as e:
            print(f"❌ [{idx}/{total_count}] 오류 발생 (ID: {record.id}, Identifier: {record.identifier})")
            print(f"   에러: {str(e)}")
            print()
            error_count += 1
            continue
    
    print()
    print("=" * 80)
    print("마이그레이션 완료")
    print("=" * 80)
    print(f"📊 통계:")
    print(f"   - 전체 레코드: {total_count}")
    print(f"   - 마이그레이션: {migrated_count}")
    print(f"   - 스킵: {skipped_count}")
    print(f"   - 오류: {error_count}")
    
    if dry_run:
        print()
        print("⚠️ DRY-RUN 모드였습니다. 실제 변경은 없었습니다.")
        print("실제 마이그레이션을 수행하려면 --dry-run 옵션 없이 실행하세요.")


def cleanup_empty_directories(dry_run=False):
    """비어있는 카테고리 디렉토리 정리"""
    
    print()
    print("=" * 80)
    print("빈 디렉토리 정리")
    print("=" * 80)
    
    media_root = Path(settings.MEDIA_ROOT)
    audio_dir = media_root / 'audio'
    
    removed_count = 0
    
    for category_dir in audio_dir.iterdir():
        if not category_dir.is_dir():
            continue
        
        # 카테고리 디렉토리 내의 파일 및 폴더 확인
        items = list(category_dir.iterdir())
        
        # JSON 파일만 있는 경우나 완전히 비어있는 경우
        has_audio = any(
            item.is_file() and item.suffix.lower() in ['.wav', '.mp3', '.m4a', '.flac']
            for item in items
        )
        
        if not has_audio and not any(item.is_dir() for item in items):
            # 오디오 파일도 없고 하위 디렉토리도 없음 (JSON만 있거나 완전히 비어있음)
            print(f"🗑️  {category_dir.name}/ (빈 디렉토리 또는 JSON만 존재)")
            
            if not dry_run:
                # JSON 파일들도 함께 삭제하지 않고 남겨둘지 선택 가능
                # 여기서는 완전히 비어있는 경우만 삭제
                if len(items) == 0:
                    category_dir.rmdir()
                    removed_count += 1
                    print(f"   ✅ 삭제됨")
                else:
                    print(f"   ⚠️  JSON 파일이 있어 유지됨")
            else:
                print(f"   [DRY-RUN] 실제 실행 시 삭제됨")
    
    print(f"\n정리된 디렉토리 수: {removed_count}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='오디오 파일을 identifier 기반 폴더 구조로 마이그레이션'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 변경 없이 테스트만 수행'
    )
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='마이그레이션 후 빈 디렉토리 정리'
    )
    
    args = parser.parse_args()
    
    try:
        migrate_audio_files(dry_run=args.dry_run)
        
        if args.cleanup:
            cleanup_empty_directories(dry_run=args.dry_run)
        
        print()
        print("✅ 스크립트 실행 완료")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 치명적 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
