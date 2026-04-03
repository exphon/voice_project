#!/usr/bin/env python
"""
Failed 상태 레코드 분석
전사 실패(failed) 상태인 파일들의 상세 분석
"""

import os
import sys
import django
from collections import defaultdict

# Django 설정
sys.path.append('/var/www/html/dj_voice_manage')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_project.settings')
django.setup()

from django.db.models import Count, Q
from voice_app.models import AudioRecord


def analyze_failed_records():
    """Failed 상태 레코드 상세 분석"""
    
    print("=" * 80)
    print("전사 실패(Failed) 레코드 분석")
    print("=" * 80)
    print()
    
    # 전체 failed 레코드
    total_failed = AudioRecord.objects.filter(status='failed').count()
    total_records = AudioRecord.objects.count()
    
    print(f"📊 전체 현황:")
    print(f"  총 레코드: {total_records:,}개")
    print(f"  Failed 상태: {total_failed:,}개 ({total_failed/total_records*100:.2f}%)")
    print()
    
    if total_failed == 0:
        print("✓ Failed 상태인 레코드가 없습니다.")
        return
    
    # ===== 1. 카테고리별 Failed 분포 =====
    print("=" * 80)
    print("1. 카테고리별 Failed 분포")
    print("=" * 80)
    print()
    
    categories = {
        'child': '아동',
        'senior': '성인',
        'atypical': '음성 장애',
        'auditory': '청각 장애',
        'normal': '일반'
    }
    
    for category_code, category_name in categories.items():
        cat_total = AudioRecord.objects.filter(category=category_code).count()
        cat_failed = AudioRecord.objects.filter(
            category=category_code,
            status='failed'
        ).count()
        
        if cat_total > 0:
            percentage = (cat_failed / cat_total) * 100
            bar = "█" * int(percentage / 2) if percentage > 0 else ""
            print(f"  {category_name:10s}: {cat_failed:4,}개 / {cat_total:6,}개 ({percentage:5.2f}%) {bar}")
    
    print()
    
    # ===== 2. Identifier별 Failed 분석 =====
    print("=" * 80)
    print("2. Identifier별 Failed 분석")
    print("=" * 80)
    print()
    
    # Identifier가 있는 failed 레코드
    failed_with_identifier = AudioRecord.objects.filter(
        status='failed'
    ).exclude(
        Q(identifier__isnull=True) | Q(identifier='')
    ).values('identifier', 'category').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Identifier가 없는 failed 레코드
    failed_without_identifier = AudioRecord.objects.filter(
        status='failed',
        identifier__isnull=True
    ).count() + AudioRecord.objects.filter(
        status='failed',
        identifier=''
    ).count()
    
    print(f"Identifier 있음: {len(failed_with_identifier)}개 identifier")
    print(f"Identifier 없음: {failed_without_identifier}개 레코드")
    print()
    
    if failed_with_identifier:
        print("Identifier별 Failed 건수 (상위 20개):")
        for idx, item in enumerate(failed_with_identifier[:20], 1):
            cat_name = categories.get(item['category'], item['category'])
            print(f"  {idx:2d}. {item['identifier']} ({cat_name}): {item['count']}개")
        
        if len(failed_with_identifier) > 20:
            print(f"  ... (외 {len(failed_with_identifier) - 20}개 identifier)")
        print()
    
    # ===== 3. Identifier별 Failed 비율 분석 =====
    print("=" * 80)
    print("3. Identifier별 Failed 비율 (전체 파일 대비)")
    print("=" * 80)
    print()
    
    # 각 identifier의 전체 파일 수와 failed 수 비교
    identifiers_with_failed = set(item['identifier'] for item in failed_with_identifier)
    
    identifier_analysis = []
    for identifier in identifiers_with_failed:
        total_files = AudioRecord.objects.filter(identifier=identifier).count()
        failed_files = AudioRecord.objects.filter(
            identifier=identifier,
            status='failed'
        ).count()
        
        failed_ratio = (failed_files / total_files) * 100 if total_files > 0 else 0
        
        identifier_analysis.append({
            'identifier': identifier,
            'total': total_files,
            'failed': failed_files,
            'failed_ratio': failed_ratio,
            'category': AudioRecord.objects.filter(identifier=identifier).first().category
        })
    
    # Failed 비율 기준 내림차순 정렬
    identifier_analysis.sort(key=lambda x: x['failed_ratio'], reverse=True)
    
    print(f"Failed 비율 높은 Identifier (상위 20개):")
    for idx, item in enumerate(identifier_analysis[:20], 1):
        cat_name = categories.get(item['category'], item['category'])
        print(f"  {idx:2d}. {item['identifier']} ({cat_name}): "
              f"{item['failed']}/{item['total']}개 ({item['failed_ratio']:.1f}%)")
    
    if len(identifier_analysis) > 20:
        print(f"  ... (외 {len(identifier_analysis) - 20}개 identifier)")
    print()
    
    # 100% failed인 identifier
    all_failed = [item for item in identifier_analysis if item['failed_ratio'] == 100]
    if all_failed:
        print(f"⚠ 전체 파일이 Failed인 Identifier: {len(all_failed)}개")
        for item in all_failed[:10]:
            cat_name = categories.get(item['category'], item['category'])
            print(f"  - {item['identifier']} ({cat_name}): {item['total']}개 전부 failed")
        if len(all_failed) > 10:
            print(f"  ... (외 {len(all_failed) - 10}개)")
        print()
    
    # ===== 4. Failed 레코드 상세 정보 (샘플) =====
    print("=" * 80)
    print("4. Failed 레코드 상세 정보 (샘플 10개)")
    print("=" * 80)
    print()
    
    failed_samples = AudioRecord.objects.filter(
        status='failed'
    ).values(
        'id', 'identifier', 'category', 'audio_file', 'transcript', 
        'created_at', 'updated_at'
    )[:10]
    
    for idx, record in enumerate(failed_samples, 1):
        cat_name = categories.get(record['category'], record['category'])
        identifier = record['identifier'] or '(없음)'
        has_transcript = 'O' if record['transcript'] else 'X'
        
        print(f"{idx}. ID {record['id']}")
        print(f"   Identifier: {identifier}")
        print(f"   카테고리: {cat_name}")
        print(f"   파일: {record['audio_file']}")
        print(f"   전사 존재: {has_transcript}")
        print(f"   생성: {record['created_at'].strftime('%Y-%m-%d %H:%M:%S') if record['created_at'] else 'N/A'}")
        print()
    
    # ===== 5. Failed vs Unprocessed 비교 =====
    print("=" * 80)
    print("5. Failed vs Unprocessed 비교")
    print("=" * 80)
    print()
    
    total_unprocessed = AudioRecord.objects.filter(status='unprocessed').count()
    total_completed = AudioRecord.objects.filter(status='completed').count()
    
    print(f"상태별 분포:")
    print(f"  Completed:    {total_completed:6,}개 ({total_completed/total_records*100:5.1f}%)")
    print(f"  Unprocessed:  {total_unprocessed:6,}개 ({total_unprocessed/total_records*100:5.1f}%)")
    print(f"  Failed:       {total_failed:6,}개 ({total_failed/total_records*100:5.1f}%)")
    print()
    
    # Failed + Unprocessed = 전사 안된 레코드
    not_transcribed = total_failed + total_unprocessed
    print(f"전사 안된 레코드 (Failed + Unprocessed):")
    print(f"  총 {not_transcribed:,}개 ({not_transcribed/total_records*100:.1f}%)")
    print(f"  - Failed:      {total_failed:,}개 ({total_failed/not_transcribed*100:.1f}%)")
    print(f"  - Unprocessed: {total_unprocessed:,}개 ({total_unprocessed/not_transcribed*100:.1f}%)")
    print()
    
    # ===== 6. 2,750개 기준 환산 =====
    print("=" * 80)
    print("6. 연구 기준(2,750개) 환산")
    print("=" * 80)
    print()
    
    failed_ratio = total_failed / total_records
    unprocessed_ratio = total_unprocessed / total_records
    not_transcribed_ratio = not_transcribed / total_records
    
    estimated_failed_2750 = int(2750 * failed_ratio)
    estimated_unprocessed_2750 = int(2750 * unprocessed_ratio)
    estimated_not_transcribed_2750 = int(2750 * not_transcribed_ratio)
    
    print(f"2,750개 기준 예상:")
    print(f"  Failed 예상:          약 {estimated_failed_2750}개 ({failed_ratio*100:.2f}%)")
    print(f"  Unprocessed 예상:     약 {estimated_unprocessed_2750}개 ({unprocessed_ratio*100:.2f}%)")
    print(f"  전사 안된 파일 총계:  약 {estimated_not_transcribed_2750}개 ({not_transcribed_ratio*100:.2f}%)")
    
    print()
    print("=" * 80)
    print("분석 완료")
    print("=" * 80)


if __name__ == '__main__':
    analyze_failed_records()
