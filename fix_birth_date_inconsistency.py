#!/usr/bin/env python
"""
동일 인물의 생년월일 불일치 검사 및 수정 스크립트

동일한 identifier + 이름을 가진 사람인데 생년월일이 다른 경우를 찾아
데이터 입력 오류를 수정합니다.
"""

import os
import sys
import django
from collections import defaultdict
from datetime import datetime

# Django 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_project.settings')
django.setup()

from voice_app.models import AudioRecord


def check_birth_date_inconsistency():
    """동일 인물의 생년월일 불일치 검사"""
    
    print("=" * 80)
    print("동일 인물의 생년월일 불일치 검사")
    print("=" * 80)
    print()
    
    # identifier + name별로 그룹화
    person_data = defaultdict(lambda: {
        'birth_dates': defaultdict(list),  # 생년월일 -> 레코드 ID 리스트
        'records': []
    })
    
    # identifier가 있고 이름이 있는 모든 레코드 조회
    voices = AudioRecord.objects.filter(
        identifier__isnull=False,
        name__isnull=False
    ).exclude(
        identifier='',
        name=''
    ).order_by('identifier', 'name', 'created_at')
    
    total_count = voices.count()
    print(f"총 {total_count}개의 레코드를 검사 중...\n")
    
    if total_count == 0:
        print("검사할 데이터가 없습니다.")
        return
    
    # 데이터 수집
    for voice in voices:
        key = (voice.identifier, voice.name.strip())
        person_data[key]['records'].append(voice)
        
        if voice.birth_year and voice.birth_month and voice.birth_day:
            birth_date = f"{voice.birth_year}-{voice.birth_month.zfill(2)}-{voice.birth_day.zfill(2)}"
            person_data[key]['birth_dates'][birth_date].append({
                'id': voice.id,
                'created_at': voice.created_at,
                'category': voice.get_category_display()
            })
    
    # 불일치 검사
    inconsistencies = []
    
    for (identifier, name), data in sorted(person_data.items()):
        birth_dates = data['birth_dates']
        
        # 생년월일이 2개 이상 있는 경우
        if len(birth_dates) > 1:
            inconsistencies.append({
                'identifier': identifier,
                'name': name,
                'birth_dates': birth_dates,
                'total_records': len(data['records'])
            })
    
    # 결과 출력
    if inconsistencies:
        print("⚠️  생년월일 불일치 발견!")
        print("=" * 80)
        print()
        
        for idx, item in enumerate(inconsistencies, 1):
            identifier = item['identifier']
            name = item['name']
            birth_dates = item['birth_dates']
            total_records = item['total_records']
            
            print(f"{idx}. Identifier: {identifier}, 이름: {name}")
            print(f"   총 {total_records}개 레코드, {len(birth_dates)}개의 서로 다른 생년월일")
            print()
            
            # 생년월일별 상세 정보
            sorted_birth_dates = sorted(
                birth_dates.items(),
                key=lambda x: len(x[1]),
                reverse=True
            )
            
            for birth_date, records in sorted_birth_dates:
                print(f"   📅 {birth_date} - {len(records)}개 레코드")
                
                # 처음 3개만 표시
                for record in records[:3]:
                    created_date = record['created_at'].strftime('%Y-%m-%d %H:%M') if record['created_at'] else '알 수 없음'
                    print(f"      - ID: {record['id']}, 카테고리: {record['category']}, 업로드: {created_date}")
                
                if len(records) > 3:
                    print(f"      ... 외 {len(records) - 3}개")
                print()
            
            # 가장 많이 사용된 생년월일 제안
            most_common_birth_date = sorted_birth_dates[0][0]
            most_common_count = len(sorted_birth_dates[0][1])
            
            print(f"   💡 권장: '{most_common_birth_date}' ({most_common_count}개 레코드에서 사용)")
            print("-" * 80)
            print()
    
    # 요약
    print("=" * 80)
    print("검사 결과 요약")
    print("=" * 80)
    print(f"총 검사 인원: {len(person_data)}명")
    print(f"생년월일 불일치: {len(inconsistencies)}명")
    
    if inconsistencies:
        print()
        print("⚠️  조치 필요:")
        print("   동일 인물의 생년월일이 다르게 입력되어 있습니다.")
        print("   아래 명령으로 자동 수정할 수 있습니다:")
        print()
        print("   python3 fix_birth_date_inconsistency.py")
    else:
        print()
        print("✅ 모든 인물의 생년월일이 일관됩니다!")
    
    print("=" * 80)
    
    return inconsistencies


def fix_birth_date_inconsistency(dry_run=True):
    """생년월일 불일치 자동 수정"""
    
    print("=" * 80)
    print("생년월일 불일치 자동 수정")
    print("=" * 80)
    print()
    
    if dry_run:
        print("🔍 DRY RUN 모드 (실제 수정 안 함)")
        print()
    
    # identifier + name별로 그룹화
    person_data = defaultdict(lambda: {
        'birth_dates': defaultdict(list),
        'records': []
    })
    
    voices = AudioRecord.objects.filter(
        identifier__isnull=False,
        name__isnull=False
    ).exclude(
        identifier='',
        name=''
    )
    
    for voice in voices:
        key = (voice.identifier, voice.name.strip())
        person_data[key]['records'].append(voice)
        
        if voice.birth_year and voice.birth_month and voice.birth_day:
            birth_date = (voice.birth_year, voice.birth_month, voice.birth_day)
            person_data[key]['birth_dates'][birth_date].append(voice)
    
    # 수정 작업
    fixed_count = 0
    total_inconsistencies = 0
    
    for (identifier, name), data in sorted(person_data.items()):
        birth_dates = data['birth_dates']
        
        if len(birth_dates) <= 1:
            continue
        
        total_inconsistencies += 1
        
        # 가장 많이 사용된 생년월일 찾기
        most_common_birth_date = max(
            birth_dates.items(),
            key=lambda x: len(x[1])
        )[0]
        
        correct_year, correct_month, correct_day = most_common_birth_date
        
        # 다른 생년월일을 가진 레코드 수정
        for birth_date, records in birth_dates.items():
            if birth_date != most_common_birth_date:
                for record in records:
                    old_birth_date = f"{record.birth_year}-{record.birth_month.zfill(2)}-{record.birth_day.zfill(2)}"
                    new_birth_date = f"{correct_year}-{correct_month.zfill(2)}-{correct_day.zfill(2)}"
                    
                    print(f"수정: ID {record.id}, {identifier}, {name}")
                    print(f"  {old_birth_date} → {new_birth_date}")
                    
                    if not dry_run:
                        record.birth_year = correct_year
                        record.birth_month = correct_month
                        record.birth_day = correct_day
                        record.save()
                        print(f"  ✅ 저장 완료")
                    
                    fixed_count += 1
        
        print()
    
    # 요약
    print("=" * 80)
    print("수정 결과")
    print("=" * 80)
    print(f"불일치 발견: {total_inconsistencies}명")
    print(f"수정된 레코드: {fixed_count}개")
    
    if dry_run:
        print()
        print("⚠️  DRY RUN 모드였습니다. 실제 수정은 수행되지 않았습니다.")
        print("실제 수정하려면:")
        print("  python3 fix_birth_date_inconsistency.py --apply")
    else:
        print()
        print("✅ 수정이 완료되었습니다!")
    
    print("=" * 80)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='생년월일 불일치 검사 및 수정')
    parser.add_argument('--fix', action='store_true', help='불일치 수정 (dry run)')
    parser.add_argument('--apply', action='store_true', help='실제로 수정 적용')
    parser.add_argument('-y', '--yes', action='store_true', help='확인 없이 자동 적용')
    
    args = parser.parse_args()
    
    try:
        if args.fix or args.apply:
            # --apply인 경우 확인 받기
            if args.apply and not args.yes:
                print()
                print("⚠️  실제로 데이터베이스를 수정합니다!")
                print()
                response = input("계속하시겠습니까? (yes/no): ").strip().lower()
                if response not in ['yes', 'y']:
                    print("취소되었습니다.")
                    sys.exit(0)
                print()
            
            fix_birth_date_inconsistency(dry_run=not args.apply)
        else:
            inconsistencies = check_birth_date_inconsistency()
            
            # 불일치가 있으면 수정 여부 묻기
            if inconsistencies:
                print()
                try:
                    response = input("지금 수정하시겠습니까? (y/n): ").strip().lower()
                    if response in ['y', 'yes']:
                        print()
                        fix_birth_date_inconsistency(dry_run=False)
                except (EOFError, KeyboardInterrupt):
                    print("\n스킵됨")
    except KeyboardInterrupt:
        print("\n\n작업이 중단되었습니다.")
        sys.exit(0)
