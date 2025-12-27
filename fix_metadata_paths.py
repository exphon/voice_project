#!/usr/bin/env python
"""
metadata_path를 identifier 기반 폴더 구조로 업데이트

기존: audio/child/abc123.json
새로: audio/child/C12345/abc123.json
"""

import os
import sys
import django
import json

# Django 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_project.settings')
django.setup()

from voice_app.models import AudioRecord

def fix_metadata_paths(dry_run=False):
    """metadata_path를 identifier 기반 구조로 수정"""
    
    print("=" * 80)
    print("metadata_path 수정 시작")
    print(f"모드: {'DRY-RUN (실제 변경 없음)' if dry_run else '실제 업데이트'}")
    print("=" * 80)
    print()
    
    # identifier가 있고 metadata_path가 있는 레코드 조회
    records = AudioRecord.objects.filter(
        identifier__isnull=False,
        category_specific_data__metadata_path__isnull=False
    ).exclude(identifier='')
    
    total_count = records.count()
    print(f"📊 처리할 레코드 수: {total_count}")
    print()
    
    if total_count == 0:
        print("⚠️ 수정할 레코드가 없습니다.")
        return
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    for idx, record in enumerate(records, 1):
        try:
            metadata_path = record.category_specific_data.get('metadata_path')
            
            if not metadata_path:
                skipped_count += 1
                continue
            
            # 이미 올바른 구조인지 확인
            # 경로 구조: audio/{category}/{identifier}/{filename}.json
            if f'/{record.identifier}/' in metadata_path:
                print(f"✓ [{idx}/{total_count}] 이미 올바른 경로: {record.identifier} - {metadata_path}")
                skipped_count += 1
                continue
            
            # 새 경로 생성
            # 기존: audio/child/abc123.json
            # 새로: audio/child/C12345/abc123.json
            parts = metadata_path.split('/')
            if len(parts) >= 3:
                category = parts[1]
                filename = parts[-1]
                new_metadata_path = f'audio/{category}/{record.identifier}/{filename}'
                
                print(f"🔄 [{idx}/{total_count}] {record.identifier}")
                print(f"   현재: {metadata_path}")
                print(f"   새 경로: {new_metadata_path}")
                
                if not dry_run:
                    # category_specific_data 업데이트
                    record.category_specific_data['metadata_path'] = new_metadata_path
                    record.save(update_fields=['category_specific_data'])
                    print(f"   ✅ 업데이트 완료")
                else:
                    print(f"   [DRY-RUN] 실제 실행 시 업데이트됨")
                
                updated_count += 1
                print()
            else:
                print(f"⚠️  [{idx}/{total_count}] 경로 형식 오류: {metadata_path}")
                skipped_count += 1
                
        except Exception as e:
            print(f"❌ [{idx}/{total_count}] 오류 (ID: {record.id}, Identifier: {record.identifier})")
            print(f"   에러: {str(e)}")
            print()
            error_count += 1
            continue
    
    print()
    print("=" * 80)
    print("metadata_path 수정 완료")
    print("=" * 80)
    print(f"📊 통계:")
    print(f"   - 전체 레코드: {total_count}")
    print(f"   - 업데이트: {updated_count}")
    print(f"   - 스킵: {skipped_count}")
    print(f"   - 오류: {error_count}")
    
    if dry_run:
        print()
        print("⚠️ DRY-RUN 모드였습니다. 실제 변경은 없었습니다.")
        print("실제 업데이트를 수행하려면 --dry-run 옵션 없이 실행하세요.")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='metadata_path를 identifier 기반 폴더 구조로 업데이트'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 변경 없이 테스트만 수행'
    )
    
    args = parser.parse_args()
    
    try:
        fix_metadata_paths(dry_run=args.dry_run)
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
