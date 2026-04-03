#!/usr/bin/env python
"""
동일한 identifier를 가진 화자들의 생년월일 일치 여부를 검사하는 스크립트
"""

import os
import sys
import django
from collections import defaultdict

# Django 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_project.settings')
django.setup()

from voice_app.models import AudioRecord


def check_birth_dates_by_identifier():
    """동일한 identifier를 가진 화자들의 생년월일이 일치하는지 검사"""
    
    print("=" * 80)
    print("동일한 identifier를 가진 화자들의 생년월일 일치 여부 검사")
    print("=" * 80)
    print()
    
    # identifier별로 화자 정보 그룹화
    identifier_groups = defaultdict(list)
    
    # identifier가 있는 모든 레코드 조회
    voices = AudioRecord.objects.filter(identifier__isnull=False).exclude(identifier='')
    total_count = voices.count()
    
    print(f"총 {total_count}개의 identifier가 있는 레코드를 찾았습니다.\n")
    
    if total_count == 0:
        print("검사할 데이터가 없습니다.")
        return
    
    # identifier별로 그룹화
    for voice in voices:
        birth_date = None
        if voice.birth_year and voice.birth_month and voice.birth_day:
            birth_date = f"{voice.birth_year}-{voice.birth_month.zfill(2)}-{voice.birth_day.zfill(2)}"
        
        identifier_groups[voice.identifier].append({
            'id': voice.id,
            'name': voice.name or '(이름 없음)',
            'birth_year': voice.birth_year,
            'birth_month': voice.birth_month,
            'birth_day': voice.birth_day,
            'birth_date': birth_date,
            'category': voice.get_category_display(),
            'created_at': voice.created_at.strftime('%Y-%m-%d %H:%M:%S') if voice.created_at else '(없음)',
            'updated_at': voice.updated_at.strftime('%Y-%m-%d %H:%M:%S') if voice.updated_at else '(없음)',
        })
    
    print(f"총 {len(identifier_groups)}개의 고유 identifier를 찾았습니다.\n")
    print("-" * 80)
    
    # 동일한 identifier를 가진 레코드가 2개 이상인 경우만 검사
    inconsistent_identifiers = []
    consistent_identifiers = []
    single_record_identifiers = []
    
    for identifier, records in sorted(identifier_groups.items()):
        if len(records) == 1:
            single_record_identifiers.append(identifier)
            continue
        
        # 생년월일 수집
        birth_dates = set()
        for record in records:
            if record['birth_date']:
                birth_dates.add(record['birth_date'])
        
        # 생년월일이 2개 이상이면 불일치
        if len(birth_dates) > 1:
            inconsistent_identifiers.append(identifier)
            print(f"\n⚠️  불일치 발견: {identifier}")
            print(f"   총 {len(records)}개 레코드, {len(birth_dates)}개의 서로 다른 생년월일")
            print()
            
            for record in records:
                birth_info = record['birth_date'] if record['birth_date'] else '(생년월일 없음)'
                print(f"   - ID: {record['id']}, 이름: {record['name']}, "
                      f"카테고리: {record['category']}, 생년월일: {birth_info}")
                print(f"     업로드: {record['created_at']}, 수정: {record['updated_at']}")
            
            print("-" * 80)
        
        elif len(birth_dates) == 1:
            consistent_identifiers.append(identifier)
        
        else:  # 모든 레코드에 생년월일이 없는 경우
            consistent_identifiers.append(identifier)
    
    # 요약 출력
    print("\n" + "=" * 80)
    print("검사 결과 요약")
    print("=" * 80)
    print(f"총 identifier 수: {len(identifier_groups)}")
    print(f"  - 단일 레코드: {len(single_record_identifiers)}개")
    print(f"  - 복수 레코드 (일치): {len(consistent_identifiers)}개")
    print(f"  - 복수 레코드 (불일치): {len(inconsistent_identifiers)}개")
    print()
    
    if inconsistent_identifiers:
        print("⚠️  생년월일이 일치하지 않는 identifier 목록:")
        for identifier in inconsistent_identifiers:
            print(f"   - {identifier} ({len(identifier_groups[identifier])}개 레코드)")
        print()
        print("⚠️  위의 identifier들은 동일한 화자임에도 서로 다른 생년월일을 가지고 있습니다.")
        print("   데이터 정합성을 위해 확인 및 수정이 필요합니다.")
    else:
        print("✅ 모든 identifier의 생년월일이 일치합니다!")
    
    print("=" * 80)
    
    # 상세 정보 출력 옵션
    if consistent_identifiers:
        print(f"\n일치하는 identifier 상세 정보를 보시겠습니까? (y/n): ", end='')
        try:
            response = input().strip().lower()
            if response == 'y':
                print("\n" + "=" * 80)
                print("일치하는 identifier 상세 정보")
                print("=" * 80)
                for identifier in sorted(consistent_identifiers):
                    records = identifier_groups[identifier]
                    if len(records) > 1:
                        birth_date = records[0]['birth_date'] if records[0]['birth_date'] else '(생년월일 없음)'
                        print(f"\n✅ {identifier} ({len(records)}개 레코드)")
                        print(f"   공통 생년월일: {birth_date}")
                        for record in records:
                            print(f"   - ID: {record['id']}, 이름: {record['name']}, "
                                  f"카테고리: {record['category']}")
                            print(f"     업로드: {record['created_at']}, 수정: {record['updated_at']}")
        except (EOFError, KeyboardInterrupt):
            print("\n스킵됨")


if __name__ == '__main__':
    try:
        check_birth_dates_by_identifier()
    except KeyboardInterrupt:
        print("\n\n검사가 중단되었습니다.")
        sys.exit(0)
