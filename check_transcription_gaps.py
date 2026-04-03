#!/usr/bin/env python
"""
동일 identifier의 음성 파일 중 전사 누락 파일 분석 스크립트

조건:
- 동일 ID의 모든 파일이 전사되지 않았으면 무시
- 일부만 전사된 경우, 전체 대비 전사 누락 비율 계산
"""

import os
import sys
import django

# Django 설정
sys.path.append('/var/www/html/dj_voice_manage')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_project.settings')
django.setup()

from django.db.models import Count, Q, F
from voice_app.models import AudioRecord
from collections import defaultdict


def analyze_transcription_gaps():
    """전사 누락 상태 분석"""
    
    print("=" * 80)
    print("음성 파일 전사 누락 분석")
    print("=" * 80)
    print()
    
    # identifier가 있는 모든 레코드 가져오기
    records = AudioRecord.objects.filter(
        identifier__isnull=False
    ).exclude(
        identifier=''
    ).values('id', 'identifier', 'transcript', 'manual_transcript', 'status', 'audio_file')
    
    # identifier별로 그룹화
    identifier_groups = defaultdict(list)
    for record in records:
        identifier_groups[record['identifier']].append(record)
    
    print(f"총 identifier 수: {len(identifier_groups)}")
    print(f"총 음성 파일 수: {len(records)}")
    print()
    
    # 분석 결과
    all_transcribed_count = 0
    all_not_transcribed_count = 0
    partial_transcribed_count = 0
    
    partial_transcribed_details = []
    
    for identifier, files in identifier_groups.items():
        total_files = len(files)
        
        # 전사 여부 확인 (transcript 또는 manual_transcript가 있으면 전사됨)
        transcribed_files = [
            f for f in files 
            if (f['transcript'] and f['transcript'].strip()) or 
               (f['manual_transcript'] and f['manual_transcript'].strip())
        ]
        transcribed_count = len(transcribed_files)
        not_transcribed_count = total_files - transcribed_count
        
        if transcribed_count == 0:
            # 모두 전사되지 않음 - 무시
            all_not_transcribed_count += 1
        elif transcribed_count == total_files:
            # 모두 전사됨
            all_transcribed_count += 1
        else:
            # 일부만 전사됨
            partial_transcribed_count += 1
            missing_percentage = (not_transcribed_count / total_files) * 100
            
            partial_transcribed_details.append({
                'identifier': identifier,
                'total': total_files,
                'transcribed': transcribed_count,
                'not_transcribed': not_transcribed_count,
                'missing_percentage': missing_percentage,
                'files': files
            })
    
    # 결과 출력
    print("=" * 80)
    print("전체 통계")
    print("=" * 80)
    print(f"모두 전사된 identifier: {all_transcribed_count}")
    print(f"전혀 전사되지 않은 identifier: {all_not_transcribed_count} (무시됨)")
    print(f"일부만 전사된 identifier: {partial_transcribed_count}")
    print()
    
    if partial_transcribed_count > 0:
        print("=" * 80)
        print("일부만 전사된 identifier 상세 정보")
        print("=" * 80)
        print()
        
        # 누락 비율 기준 내림차순 정렬
        partial_transcribed_details.sort(key=lambda x: x['missing_percentage'], reverse=True)
        
        total_files_partial = sum(d['total'] for d in partial_transcribed_details)
        total_not_transcribed = sum(d['not_transcribed'] for d in partial_transcribed_details)
        overall_missing_percentage = (total_not_transcribed / total_files_partial) * 100 if total_files_partial > 0 else 0
        
        print(f"일부만 전사된 그룹의 전체 파일 수: {total_files_partial}")
        print(f"일부만 전사된 그룹의 전사 누락 파일 수: {total_not_transcribed}")
        print(f"일부만 전사된 그룹의 전체 전사 누락 비율: {overall_missing_percentage:.2f}%")
        print()
        print("-" * 80)
        
        for idx, detail in enumerate(partial_transcribed_details, 1):
            print(f"\n{idx}. Identifier: {detail['identifier']}")
            print(f"   전체 파일: {detail['total']}개")
            print(f"   전사 완료: {detail['transcribed']}개")
            print(f"   전사 누락: {detail['not_transcribed']}개")
            print(f"   누락 비율: {detail['missing_percentage']:.2f}%")
            
            # 누락된 파일 목록
            not_transcribed_files = [
                f for f in detail['files'] 
                if not ((f['transcript'] and f['transcript'].strip()) or 
                       (f['manual_transcript'] and f['manual_transcript'].strip()))
            ]
            
            if not_transcribed_files:
                print(f"   누락 파일:")
                for f in not_transcribed_files:
                    print(f"     - ID {f['id']}: {f['audio_file']} (상태: {f['status']})")
        
        print()
        print("=" * 80)
    
    # 전체 요약
    print()
    print("=" * 80)
    print("최종 요약")
    print("=" * 80)
    
    if partial_transcribed_count == 0:
        print("✓ 일부만 전사된 identifier가 없습니다.")
        print("  모든 identifier는 전부 전사되었거나 전혀 전사되지 않았습니다.")
    else:
        total_files_partial = sum(d['total'] for d in partial_transcribed_details)
        total_not_transcribed = sum(d['not_transcribed'] for d in partial_transcribed_details)
        overall_missing_percentage = (total_not_transcribed / total_files_partial) * 100
        
        print(f"⚠ {partial_transcribed_count}개의 identifier에서 일부 전사 누락 발견")
        print(f"  - 해당 그룹의 총 파일 수: {total_files_partial}개")
        print(f"  - 전사 누락 파일 수: {total_not_transcribed}개")
        print(f"  - 전체 대비 누락 비율: {overall_missing_percentage:.2f}%")
    
    print()


if __name__ == '__main__':
    analyze_transcription_gaps()
