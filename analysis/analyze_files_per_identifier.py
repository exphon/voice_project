#!/usr/bin/env python
"""
Identifier별 음성 파일 개수 분석
카테고리별(아동, 성인 등) 한 명당 평균 음성 파일 개수 확인
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

from django.db.models import Count
from voice_app.models import AudioRecord


def analyze_files_per_identifier():
    """카테고리별 identifier당 파일 개수 분석"""
    
    print("=" * 80)
    print("Identifier별 음성 파일 개수 분석")
    print("=" * 80)
    print()
    
    # 카테고리별로 분석
    categories = {
        'child': '아동',
        'senior': '성인',
        'atypical': '음성 장애',
        'auditory': '청각 장애',
        'normal': '일반'
    }
    
    for category_code, category_name in categories.items():
        print(f"\n{'=' * 80}")
        print(f"카테고리: {category_name} ({category_code})")
        print(f"{'=' * 80}")
        
        # 해당 카테고리의 identifier별 파일 개수
        identifier_counts = AudioRecord.objects.filter(
            category=category_code,
            identifier__isnull=False
        ).exclude(
            identifier=''
        ).values('identifier').annotate(
            file_count=Count('id')
        ).order_by('-file_count')
        
        if not identifier_counts:
            print(f"  ⚠ {category_name} 카테고리에 identifier가 지정된 파일이 없습니다.")
            continue
        
        # 통계 계산
        total_identifiers = len(identifier_counts)
        total_files = sum(item['file_count'] for item in identifier_counts)
        avg_files = total_files / total_identifiers if total_identifiers > 0 else 0
        
        file_counts_list = [item['file_count'] for item in identifier_counts]
        min_files = min(file_counts_list)
        max_files = max(file_counts_list)
        
        # 분포 계산
        distribution = defaultdict(int)
        for count in file_counts_list:
            distribution[count] += 1
        
        print(f"\n📊 전체 통계:")
        print(f"  - 총 identifier 수: {total_identifiers}명")
        print(f"  - 총 음성 파일 수: {total_files}개")
        print(f"  - 평균 파일 수/인: {avg_files:.2f}개")
        print(f"  - 최소 파일 수: {min_files}개")
        print(f"  - 최대 파일 수: {max_files}개")
        
        # 중앙값 계산
        sorted_counts = sorted(file_counts_list)
        median_idx = len(sorted_counts) // 2
        if len(sorted_counts) % 2 == 0:
            median = (sorted_counts[median_idx - 1] + sorted_counts[median_idx]) / 2
        else:
            median = sorted_counts[median_idx]
        print(f"  - 중앙값: {median:.1f}개")
        
        # 가장 흔한 파일 개수 (최빈값)
        most_common_count = max(distribution.items(), key=lambda x: x[1])
        print(f"  - 최빈값: {most_common_count[0]}개 ({most_common_count[1]}명이 해당)")
        
        # 파일 개수 분포 (상위 10개)
        print(f"\n📈 파일 개수 분포 (상위 10개):")
        for idx, item in enumerate(identifier_counts[:10], 1):
            print(f"  {idx:2d}. {item['identifier']}: {item['file_count']}개")
        
        if total_identifiers > 10:
            print(f"  ... (외 {total_identifiers - 10}명)")
        
        # 파일 개수별 identifier 분포
        print(f"\n📊 파일 개수별 분포:")
        sorted_distribution = sorted(distribution.items(), key=lambda x: x[0])
        
        # 그룹화하여 표시 (1-10, 11-20, 21-30, ... 등)
        grouped_dist = defaultdict(int)
        for count, num_identifiers in sorted_distribution:
            if count <= 10:
                group = f"1-10개"
            elif count <= 20:
                group = f"11-20개"
            elif count <= 30:
                group = f"21-30개"
            elif count <= 40:
                group = f"31-40개"
            elif count <= 50:
                group = f"41-50개"
            elif count <= 60:
                group = f"51-60개"
            elif count <= 70:
                group = f"61-70개"
            elif count <= 80:
                group = f"71-80개"
            elif count <= 90:
                group = f"81-90개"
            elif count <= 100:
                group = f"91-100개"
            else:
                group = f"100개 이상"
            grouped_dist[group] += num_identifiers
        
        for group in ["1-10개", "11-20개", "21-30개", "31-40개", "41-50개", 
                      "51-60개", "61-70개", "71-80개", "81-90개", "91-100개", "100개 이상"]:
            if group in grouped_dist:
                count = grouped_dist[group]
                percentage = (count / total_identifiers) * 100
                bar = "█" * int(percentage / 2)
                print(f"  {group:12s}: {count:4d}명 ({percentage:5.1f}%) {bar}")
    
    print("\n" + "=" * 80)
    print("분석 완료")
    print("=" * 80)


if __name__ == '__main__':
    analyze_files_per_identifier()
