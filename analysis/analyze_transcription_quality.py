#!/usr/bin/env python
"""
전사 품질 종합 분석 스크립트
- WER (Word Error Rate) 계산
- 전사 누락 현황 분석
- 카테고리별 품질 지표
"""

import os
import sys
import django
from collections import defaultdict
import re

# Django 설정 - analysis 폴더에서 실행하므로 상위 디렉토리 참조
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_project.settings')
django.setup()

from django.db.models import Count, Q, Avg, F
from voice_app.models import AudioRecord
from datetime import datetime, timedelta


def calculate_wer(reference, hypothesis):
    """
    Word Error Rate (WER) 계산
    WER = (S + D + I) / N
    S: Substitutions, D: Deletions, I: Insertions, N: Total words in reference
    """
    # 텍스트 정규화
    ref_words = reference.strip().split()
    hyp_words = hypothesis.strip().split()
    
    # Levenshtein distance 계산 (단어 레벨)
    n = len(ref_words)
    m = len(hyp_words)
    
    if n == 0:
        return 0.0 if m == 0 else float('inf')
    
    # DP 테이블
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i-1] == hyp_words[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = min(
                    dp[i-1][j] + 1,      # Deletion
                    dp[i][j-1] + 1,      # Insertion
                    dp[i-1][j-1] + 1     # Substitution
                )
    
    wer = dp[n][m] / n if n > 0 else 0.0
    return wer * 100  # 백분율로 반환


def normalize_text(text):
    """텍스트 정규화 (WER 계산용)"""
    if not text:
        return ""
    
    # 소문자 변환
    text = text.lower()
    
    # 화자 라벨 제거 [SPEAKER_00] 등
    text = re.sub(r'\[SPEAKER_\d+\]', '', text)
    text = re.sub(r'\[[^\]]+\]', '', text)
    
    # 구두점 제거
    text = re.sub(r'[^\w\s가-힣]', ' ', text)
    
    # 연속 공백 제거
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def analyze_transcription_quality():
    """전사 품질 종합 분석"""
    
    print("=" * 80)
    print("전사 품질 종합 분석 보고서")
    print("=" * 80)
    print(f"분석 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # ===== 1. 전체 전사 현황 =====
    print("=" * 80)
    print("1. 전사 현황 Overview")
    print("=" * 80)
    print()
    
    total_records = AudioRecord.objects.count()
    
    # 자동 전사 있음
    with_auto_transcript = AudioRecord.objects.filter(
        transcript__isnull=False
    ).exclude(transcript='').count()
    
    # 수동 전사 있음
    with_manual_transcript = AudioRecord.objects.filter(
        manual_transcript__isnull=False
    ).exclude(manual_transcript='').count()
    
    # 둘 다 있음 (WER 계산 가능)
    both_transcripts = AudioRecord.objects.filter(
        transcript__isnull=False,
        manual_transcript__isnull=False
    ).exclude(
        transcript=''
    ).exclude(
        manual_transcript=''
    ).count()
    
    # 상태별 통계
    status_counts = AudioRecord.objects.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    print(f"총 레코드 수: {total_records:,}개")
    print(f"자동 전사 완료: {with_auto_transcript:,}개 ({with_auto_transcript/total_records*100:.1f}%)")
    print(f"수동 교정 완료: {with_manual_transcript:,}개 ({with_manual_transcript/total_records*100:.1f}%)")
    print(f"WER 계산 가능(둘 다 있음): {both_transcripts:,}개")
    print()
    
    print("상태별 분포:")
    for item in status_counts:
        status = item['status'] or 'null'
        count = item['count']
        percentage = (count / total_records) * 100
        bar = "█" * int(percentage / 2)
        print(f"  {status:15s}: {count:6,}개 ({percentage:5.1f}%) {bar}")
    print()
    
    # ===== 2. WER 분석 =====
    print("=" * 80)
    print("2. WER (Word Error Rate) 분석")
    print("=" * 80)
    print()
    
    # WER 계산 가능한 레코드만 가져오기
    records_for_wer = AudioRecord.objects.filter(
        transcript__isnull=False,
        manual_transcript__isnull=False
    ).exclude(
        transcript=''
    ).exclude(
        manual_transcript=''
    ).values('id', 'transcript', 'manual_transcript', 'category')
    
    if records_for_wer:
        wer_scores = []
        category_wer = defaultdict(list)
        
        print(f"WER 계산 중... (총 {len(records_for_wer):,}개 레코드)")
        
        for idx, record in enumerate(records_for_wer):
            if (idx + 1) % 100 == 0:
                print(f"  진행: {idx + 1:,}/{len(records_for_wer):,} ({(idx+1)/len(records_for_wer)*100:.1f}%)")
            
            ref = normalize_text(record['manual_transcript'])
            hyp = normalize_text(record['transcript'])
            
            if ref:  # reference가 비어있지 않은 경우만
                wer = calculate_wer(ref, hyp)
                if wer != float('inf'):  # 유효한 WER만
                    wer_scores.append(wer)
                    category_wer[record['category']].append(wer)
        
        print()
        
        if wer_scores:
            avg_wer = sum(wer_scores) / len(wer_scores)
            median_wer = sorted(wer_scores)[len(wer_scores) // 2]
            min_wer = min(wer_scores)
            max_wer = max(wer_scores)
            
            print(f"전체 WER 통계:")
            print(f"  평균 WER: {avg_wer:.2f}%")
            print(f"  중앙값 WER: {median_wer:.2f}%")
            print(f"  최소 WER: {min_wer:.2f}%")
            print(f"  최대 WER: {max_wer:.2f}%")
            print(f"  분석 샘플 수: {len(wer_scores):,}개")
            print()
            
            # WER 구간별 분포
            wer_distribution = defaultdict(int)
            for wer in wer_scores:
                if wer < 5:
                    wer_distribution['0-5%'] += 1
                elif wer < 10:
                    wer_distribution['5-10%'] += 1
                elif wer < 20:
                    wer_distribution['10-20%'] += 1
                elif wer < 30:
                    wer_distribution['20-30%'] += 1
                elif wer < 50:
                    wer_distribution['30-50%'] += 1
                else:
                    wer_distribution['50%+'] += 1
            
            print("WER 분포:")
            for range_name in ['0-5%', '5-10%', '10-20%', '20-30%', '30-50%', '50%+']:
                if range_name in wer_distribution:
                    count = wer_distribution[range_name]
                    percentage = (count / len(wer_scores)) * 100
                    bar = "█" * int(percentage / 2)
                    print(f"  {range_name:10s}: {count:5,}개 ({percentage:5.1f}%) {bar}")
            print()
            
            # 카테고리별 WER
            print("카테고리별 WER:")
            categories = {
                'child': '아동',
                'senior': '성인',
                'atypical': '음성 장애',
                'auditory': '청각 장애',
                'normal': '일반'
            }
            
            for category_code, category_name in categories.items():
                if category_code in category_wer and category_wer[category_code]:
                    cat_wer_scores = category_wer[category_code]
                    cat_avg_wer = sum(cat_wer_scores) / len(cat_wer_scores)
                    cat_median_wer = sorted(cat_wer_scores)[len(cat_wer_scores) // 2]
                    
                    print(f"  {category_name:10s}: 평균 {cat_avg_wer:6.2f}%, 중앙값 {cat_median_wer:6.2f}% (샘플: {len(cat_wer_scores):,}개)")
            print()
    else:
        print("⚠ WER 계산을 위한 데이터가 없습니다 (자동 전사와 수동 교정이 모두 필요)")
        print()
    
    # ===== 3. 전사 누락 분석 (identifier 기준) =====
    print("=" * 80)
    print("3. 전사 누락 현황 (Identifier 기준)")
    print("=" * 80)
    print()
    
    # identifier가 있는 레코드
    records = AudioRecord.objects.filter(
        identifier__isnull=False
    ).exclude(
        identifier=''
    ).values('id', 'identifier', 'transcript', 'manual_transcript', 'status')
    
    identifier_groups = defaultdict(list)
    for record in records:
        identifier_groups[record['identifier']].append(record)
    
    total_identifiers = len(identifier_groups)
    all_transcribed = 0
    all_not_transcribed = 0
    partial_transcribed = 0
    partial_details = []
    
    for identifier, files in identifier_groups.items():
        total_files = len(files)
        
        transcribed_files = [
            f for f in files 
            if (f['transcript'] and f['transcript'].strip()) or 
               (f['manual_transcript'] and f['manual_transcript'].strip())
        ]
        transcribed_count = len(transcribed_files)
        not_transcribed_count = total_files - transcribed_count
        
        if transcribed_count == 0:
            all_not_transcribed += 1
        elif transcribed_count == total_files:
            all_transcribed += 1
        else:
            partial_transcribed += 1
            missing_percentage = (not_transcribed_count / total_files) * 100
            partial_details.append({
                'identifier': identifier,
                'total': total_files,
                'not_transcribed': not_transcribed_count,
                'missing_percentage': missing_percentage
            })
    
    print(f"총 Identifier: {total_identifiers}개")
    print(f"  - 전부 전사됨: {all_transcribed}개")
    print(f"  - 전부 미전사: {all_not_transcribed}개 (분석 제외)")
    print(f"  - 일부만 전사: {partial_transcribed}개 ⚠")
    print()
    
    if partial_details:
        total_files_partial = sum(d['total'] for d in partial_details)
        total_not_transcribed = sum(d['not_transcribed'] for d in partial_details)
        overall_missing_rate = (total_not_transcribed / total_files_partial) * 100
        
        print(f"일부만 전사된 그룹 상세:")
        print(f"  - 해당 그룹 총 파일 수: {total_files_partial:,}개")
        print(f"  - 미전사 파일 수: {total_not_transcribed:,}개")
        print(f"  - 누락 비율: {overall_missing_rate:.2f}%")
        print()
        
        # 2,750개 기준 환산
        estimated_missing_2750 = int(2750 * overall_missing_rate / 100)
        print(f"📌 연구 기준(2,750개) 환산:")
        print(f"  - 예상 누락 파일 수: 약 {estimated_missing_2750}개 (≈{overall_missing_rate:.1f}%)")
        print()
        
        # 극단 사례 (누락률 90% 이상)
        extreme_cases = [d for d in partial_details if d['missing_percentage'] >= 90]
        if extreme_cases:
            print(f"극단 사례 (누락률 90% 이상): {len(extreme_cases)}개")
            for case in sorted(extreme_cases, key=lambda x: x['missing_percentage'], reverse=True)[:5]:
                print(f"  - {case['identifier']}: {case['total']}개 중 {case['not_transcribed']}개 미전사 ({case['missing_percentage']:.1f}%)")
            print()
    
    # ===== 4. 카테고리별 전사 현황 =====
    print("=" * 80)
    print("4. 카테고리별 전사 현황")
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
        
        if cat_total == 0:
            continue
        
        cat_auto = AudioRecord.objects.filter(
            category=category_code
        ).exclude(
            Q(transcript__isnull=True) | Q(transcript='')
        ).count()
        
        cat_manual = AudioRecord.objects.filter(
            category=category_code
        ).exclude(
            Q(manual_transcript__isnull=True) | Q(manual_transcript='')
        ).count()
        
        cat_unprocessed = AudioRecord.objects.filter(
            category=category_code,
            status='unprocessed'
        ).count()
        
        print(f"{category_name} ({category_code}):")
        print(f"  총 레코드: {cat_total:,}개")
        print(f"  자동 전사: {cat_auto:,}개 ({cat_auto/cat_total*100:.1f}%)")
        print(f"  수동 교정: {cat_manual:,}개 ({cat_manual/cat_total*100:.1f}%)")
        print(f"  미처리: {cat_unprocessed:,}개 ({cat_unprocessed/cat_total*100:.1f}%)")
        print()
    
    # ===== 5. 처리 시간 분석 (updated_at - created_at) =====
    print("=" * 80)
    print("5. 처리 시간 분석")
    print("=" * 80)
    print()
    
    # 수동 교정이 있는 레코드의 시간 차이
    records_with_times = AudioRecord.objects.filter(
        manual_transcript__isnull=False
    ).exclude(
        manual_transcript=''
    ).exclude(
        created_at__isnull=True
    ).exclude(
        updated_at__isnull=True
    ).values('created_at', 'updated_at', 'transcript', 'manual_transcript')[:1000]
    
    if records_with_times:
        time_diffs = []
        for record in records_with_times:
            time_diff = (record['updated_at'] - record['created_at']).total_seconds()
            if 0 < time_diff < 86400:  # 24시간 이내만 (비정상 값 제외)
                time_diffs.append(time_diff)
        
        if time_diffs:
            avg_time = sum(time_diffs) / len(time_diffs)
            median_time = sorted(time_diffs)[len(time_diffs) // 2]
            
            print(f"수동 교정 소요 시간 (샘플: {len(time_diffs)}개):")
            print(f"  평균: {avg_time:.1f}초 ({avg_time/60:.1f}분)")
            print(f"  중앙값: {median_time:.1f}초 ({median_time/60:.1f}분)")
            print()
            print(f"📌 발화당 평균 교정 시간: 약 {avg_time:.1f}초")
        else:
            print("⚠ 유효한 처리 시간 데이터가 없습니다.")
    else:
        print("⚠ 처리 시간 분석을 위한 데이터가 부족합니다.")
    
    print()
    print("=" * 80)
    print("분석 완료")
    print("=" * 80)


if __name__ == '__main__':
    analyze_transcription_quality()
