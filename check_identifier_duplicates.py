#!/usr/bin/env python
"""
identifier 중복 및 충돌 검사 스크립트
동일한 identifier를 가진 서로 다른 사람(생년월일이 다른 경우)을 검출합니다.
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


def check_identifier_conflicts():
    """identifier 충돌 검사 - 동일 identifier에 서로 다른 생년월일"""
    
    print("=" * 80)
    print("Identifier 중복 및 충돌 검사")
    print("=" * 80)
    print()
    
    # identifier별로 화자 정보 그룹화
    identifier_data = defaultdict(lambda: {
        'birth_dates': set(),
        'names': set(),
        'count': 0,
        'sample_ids': []
    })
    
    # identifier가 있는 모든 레코드 조회
    voices = AudioRecord.objects.filter(identifier__isnull=False).exclude(identifier='')
    total_count = voices.count()
    
    print(f"총 {total_count}개의 identifier가 있는 레코드를 검사 중...\n")
    
    if total_count == 0:
        print("검사할 데이터가 없습니다.")
        return
    
    # 데이터 수집
    for voice in voices:
        identifier = voice.identifier
        identifier_data[identifier]['count'] += 1
        
        if voice.birth_year and voice.birth_month and voice.birth_day:
            birth_date = f"{voice.birth_year}-{voice.birth_month.zfill(2)}-{voice.birth_day.zfill(2)}"
            identifier_data[identifier]['birth_dates'].add(birth_date)
        
        if voice.name:
            identifier_data[identifier]['names'].add(voice.name)
        
        if len(identifier_data[identifier]['sample_ids']) < 3:
            identifier_data[identifier]['sample_ids'].append(voice.id)
    
    # 충돌 검사
    conflicts = []
    warnings = []
    
    for identifier, data in sorted(identifier_data.items()):
        # 1. 서로 다른 생년월일이 2개 이상인 경우 (심각한 충돌)
        if len(data['birth_dates']) > 1:
            conflicts.append((identifier, data))
        # 2. 서로 다른 이름이 2개 이상인 경우 (경고)
        elif len(data['names']) > 1:
            warnings.append((identifier, data))
    
    # 충돌 출력
    if conflicts:
        print("🚨 심각한 충돌 발견 (동일 identifier, 서로 다른 생년월일)")
        print("=" * 80)
        for identifier, data in conflicts:
            print(f"\n⚠️  Identifier: {identifier}")
            print(f"   총 레코드 수: {data['count']}개")
            print(f"   서로 다른 생년월일: {len(data['birth_dates'])}개")
            for birth_date in sorted(data['birth_dates']):
                print(f"     - {birth_date}")
            if data['names']:
                print(f"   이름: {', '.join(sorted(data['names']))}")
            print(f"   샘플 레코드 ID: {', '.join(map(str, data['sample_ids']))}")
            print("-" * 80)
    
    # 경고 출력
    if warnings:
        print("\n⚠️  경고 (동일 identifier, 서로 다른 이름)")
        print("=" * 80)
        for identifier, data in warnings:
            print(f"\nIdentifier: {identifier}")
            print(f"   총 레코드 수: {data['count']}개")
            print(f"   서로 다른 이름: {', '.join(sorted(data['names']))}")
            if data['birth_dates']:
                print(f"   생년월일: {', '.join(sorted(data['birth_dates']))}")
            print(f"   샘플 레코드 ID: {', '.join(map(str, data['sample_ids']))}")
    
    # 요약
    print("\n" + "=" * 80)
    print("검사 결과 요약")
    print("=" * 80)
    print(f"총 identifier 수: {len(identifier_data)}")
    print(f"심각한 충돌 (서로 다른 생년월일): {len(conflicts)}개")
    print(f"경고 (서로 다른 이름): {len(warnings)}개")
    
    if conflicts:
        print("\n🚨 조치 필요:")
        print("   서로 다른 사람은 다른 identifier를 사용해야 합니다.")
        print("   충돌하는 identifier를 수정하거나 새로운 identifier를 부여하세요.")
    elif warnings:
        print("\n⚠️  확인 필요:")
        print("   동일 identifier에 서로 다른 이름이 있습니다.")
        print("   동일 인물의 이름 표기 차이인지 확인하세요.")
    else:
        print("\n✅ 충돌이 발견되지 않았습니다!")
    
    print("=" * 80)


def generate_new_identifier(category_prefix):
    """사용 가능한 새로운 identifier 생성 (충돌 방지)"""
    import random
    
    if category_prefix not in ['C', 'S', 'A']:
        raise ValueError("category_prefix는 C, S, 또는 A여야 합니다.")
    
    # 기존 identifier 수집
    existing_identifiers = set(
        AudioRecord.objects.filter(
            identifier__isnull=False,
            identifier__startswith=category_prefix
        ).values_list('identifier', flat=True)
    )
    
    # 새로운 identifier 생성 (최대 100번 시도)
    for _ in range(100):
        number = random.randint(10000, 99999)
        new_identifier = f"{category_prefix}{number}"
        
        if new_identifier not in existing_identifiers:
            return new_identifier
    
    raise RuntimeError(f"사용 가능한 {category_prefix} identifier를 찾을 수 없습니다.")


if __name__ == '__main__':
    try:
        check_identifier_conflicts()
        
        # 새 identifier 생성 예시
        print("\n" + "=" * 80)
        print("새 Identifier 생성 예시")
        print("=" * 80)
        try:
            new_child_id = generate_new_identifier('C')
            new_senior_id = generate_new_identifier('S')
            new_auditory_id = generate_new_identifier('A')
            
            print(f"새 아동(Child) ID: {new_child_id}")
            print(f"새 성인(Senior) ID: {new_senior_id}")
            print(f"새 청각/음성장애(Auditory/Atypical) ID: {new_auditory_id}")
        except Exception as e:
            print(f"새 ID 생성 실패: {e}")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n검사가 중단되었습니다.")
        sys.exit(0)
