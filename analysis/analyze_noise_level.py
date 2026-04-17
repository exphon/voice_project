#!/usr/bin/env python
"""
소음 수준(noise_level) 통계 분석
"""

import os
import sys
import django
from collections import defaultdict

# Django 설정 - analysis 폴더에서 실행하므로 상위 디렉토리 참조
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_project.settings')
django.setup()

from django.db.models import Count, Q
from voice_app.models import AudioRecord


def analyze_noise_level():
    """소음 수준 통계 분석"""
    
    print("=" * 80)
    print("소음 수준(Noise Level) 통계 분석")
    print("=" * 80)
    print()
    
    # 전체 통계
    total_records = AudioRecord.objects.count()
    with_noise_level = AudioRecord.objects.exclude(
        Q(noise_level__isnull=True) | Q(noise_level='')
    ).count()
    without_noise_level = total_records - with_noise_level
    
    print(f"📊 전체 현황:")
    print(f"  - 전체 레코드 수: {total_records:,}개")
    print(f"  - 소음 수준 기록됨: {with_noise_level:,}개 ({with_noise_level/total_records*100:.1f}%)")
    print(f"  - 소음 수준 미기록: {without_noise_level:,}개 ({without_noise_level/total_records*100:.1f}%)")
    print()
    
    # 소음 수준별 분포
    noise_level_counts = AudioRecord.objects.exclude(
        Q(noise_level__isnull=True) | Q(noise_level='')
    ).values('noise_level').annotate(
        count=Count('id')
    ).order_by('-count')
    
    if noise_level_counts:
        print("=" * 80)
        print("소음 수준별 분포")
        print("=" * 80)
        print()
        
        for item in noise_level_counts:
            noise_level = item['noise_level']
            count = item['count']
            percentage = (count / with_noise_level) * 100 if with_noise_level > 0 else 0
            bar = "█" * int(percentage / 2)
            print(f"  {noise_level:20s}: {count:6,}개 ({percentage:5.1f}%) {bar}")
        print()
    
    # 카테고리별 소음 수준 분포
    categories = {
        'child': '아동',
        'senior': '성인',
        'atypical': '음성 장애',
        'auditory': '청각 장애',
        'normal': '일반'
    }
    
    print("=" * 80)
    print("카테고리별 소음 수준 분포")
    print("=" * 80)
    
    for category_code, category_name in categories.items():
        category_total = AudioRecord.objects.filter(category=category_code).count()
        
        if category_total == 0:
            continue
        
        print(f"\n📂 {category_name} ({category_code})")
        print(f"   전체: {category_total:,}개")
        
        category_noise_counts = AudioRecord.objects.filter(
            category=category_code
        ).exclude(
            Q(noise_level__isnull=True) | Q(noise_level='')
        ).values('noise_level').annotate(
            count=Count('id')
        ).order_by('-count')
        
        if category_noise_counts:
            category_with_noise = sum(item['count'] for item in category_noise_counts)
            print(f"   소음 기록: {category_with_noise:,}개 ({category_with_noise/category_total*100:.1f}%)")
            print()
            
            for item in category_noise_counts:
                noise_level = item['noise_level']
                count = item['count']
                percentage = (count / category_with_noise) * 100 if category_with_noise > 0 else 0
                bar = "█" * int(percentage / 2)
                print(f"     {noise_level:18s}: {count:5,}개 ({percentage:5.1f}%) {bar}")
        else:
            print(f"   ⚠ 소음 수준 데이터 없음")
    
    # Identifier가 있는 레코드의 소음 수준
    print("\n" + "=" * 80)
    print("Identifier 포함 레코드의 소음 수준")
    print("=" * 80)
    print()
    
    with_identifier = AudioRecord.objects.exclude(
        Q(identifier__isnull=True) | Q(identifier='')
    ).count()
    
    identifier_with_noise = AudioRecord.objects.exclude(
        Q(identifier__isnull=True) | Q(identifier='')
    ).exclude(
        Q(noise_level__isnull=True) | Q(noise_level='')
    ).count()
    
    print(f"  Identifier 있는 레코드: {with_identifier:,}개")
    print(f"  그 중 소음 수준 기록: {identifier_with_noise:,}개 ({identifier_with_noise/with_identifier*100:.1f}%)")
    print()
    
    identifier_noise_counts = AudioRecord.objects.exclude(
        Q(identifier__isnull=True) | Q(identifier='')
    ).exclude(
        Q(noise_level__isnull=True) | Q(noise_level='')
    ).values('noise_level').annotate(
        count=Count('id')
    ).order_by('-count')
    
    if identifier_noise_counts:
        for item in identifier_noise_counts:
            noise_level = item['noise_level']
            count = item['count']
            percentage = (count / identifier_with_noise) * 100 if identifier_with_noise > 0 else 0
            bar = "█" * int(percentage / 2)
            print(f"  {noise_level:20s}: {count:6,}개 ({percentage:5.1f}%) {bar}")
    
    print("\n" + "=" * 80)
    print("분석 완료")
    print("=" * 80)


if __name__ == '__main__':
    analyze_noise_level()
