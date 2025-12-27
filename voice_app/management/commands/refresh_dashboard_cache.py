"""
대시보드 캐시를 갱신하는 관리 명령어
크론잡으로 매일 자동 실행하여 캐시를 최신 상태로 유지합니다.

사용법:
    python manage.py refresh_dashboard_cache

크론잡 설정 예시 (매일 새벽 3시 실행):
    0 3 * * * cd /var/www/html/dj_voice_manage && /home/USERXX/anaconda3/envs/aligner/bin/python manage.py refresh_dashboard_cache >> /var/www/html/dj_voice_manage/cache_refresh.log 2>&1
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db.models import Count, Q, Avg
from django.utils import timezone
from voice_app.models import AudioRecord
from decimal import Decimal


class Command(BaseCommand):
    help = '대시보드 및 위치 정보 통계 캐시를 갱신합니다'

    def handle(self, *args, **options):
        start_time = timezone.now()
        self.stdout.write(f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}] 캐시 갱신 시작...")
        
        try:
            # ==================== 대시보드 통계 ====================
            self.stdout.write("\n[1/2] 대시보드 통계 데이터 계산 중...")
            dashboard_start = timezone.now()
            
            # 캐시 키 정의
            DASHBOARD_CACHE_KEY = 'dashboard_statistics'
            CACHE_TIMEOUT = 86400  # 24시간
            
            # 기존 캐시 삭제
            cache.delete(DASHBOARD_CACHE_KEY)
            cache.delete(f'{DASHBOARD_CACHE_KEY}_updated_at')
            
            # 1. 총 화자 수와 파일 수
            speaker_aggregation = AudioRecord.objects.aggregate(
                total_speakers=Count('identifier', distinct=True),
                total_files=Count('id')
            )
            total_speakers = speaker_aggregation.get('total_speakers', 0)
            total_files = speaker_aggregation.get('total_files', 0)
            
            # 2. 카테고리별 화자 수
            category_speakers = {}
            for category in ['child', 'adult']:
                category_speakers[category] = AudioRecord.objects.filter(
                    category=category
                ).values('identifier').distinct().count()
            
            # 3. 성별 통계
            gender_stats = {
                'male_speakers': AudioRecord.objects.filter(
                    gender='male'
                ).values('identifier').distinct().count(),
                'female_speakers': AudioRecord.objects.filter(
                    gender='female'
                ).values('identifier').distinct().count(),
            }
            
            # 4. 상태별 통계
            status_stats = {
                'completed': AudioRecord.objects.filter(status='completed').count(),
                'processing': AudioRecord.objects.filter(status='processing').count(),
                'pending': AudioRecord.objects.filter(status='pending').count(),
                'error': AudioRecord.objects.filter(status='error').count(),
            }
            
            # 5. SNR 통계
            recordings_with_snr = AudioRecord.objects.exclude(snr_mean__isnull=True)
            avg_snr_data = recordings_with_snr.aggregate(Avg('snr_mean'))
            avg_snr = avg_snr_data.get('snr_mean__avg')
            
            snr_stats = {
                'excellent': recordings_with_snr.filter(snr_mean__gte=20).count(),
                'good': recordings_with_snr.filter(snr_mean__gte=10, snr_mean__lt=20).count(),
                'fair': recordings_with_snr.filter(snr_mean__gte=0, snr_mean__lt=10).count(),
                'poor': recordings_with_snr.filter(snr_mean__lt=0).count(),
                'average': float(avg_snr) if avg_snr else 0,
            }
            
            # 6. 월별 통계 (최근 12개월)
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            
            monthly_stats = []
            current_date = datetime.now()
            
            for i in range(11, -1, -1):
                target_date = current_date - relativedelta(months=i)
                year = target_date.year
                month = target_date.month
                
                month_recordings = AudioRecord.objects.filter(
                    created_at__year=year,
                    created_at__month=month
                )
                
                monthly_stats.append({
                    'month': f"{year}-{month:02d}",
                    'recordings': month_recordings.count(),
                    'speakers': month_recordings.values('identifier').distinct().count(),
                })
            
            # 7. 진단명별 통계
            diagnosis_stats = list(
                AudioRecord.objects.filter(category='child')
                .exclude(Q(diagnosis__isnull=True) | Q(diagnosis=''))
                .values('diagnosis')
                .annotate(
                    speaker_count=Count('identifier', distinct=True),
                    recording_count=Count('id')
                )
                .order_by('-speaker_count')[:10]
            )
            
            # 8. 카테고리별 화자 통계
            category_stats = []
            for category in ['child', 'adult']:
                identifiers = AudioRecord.objects.filter(
                    category=category
                ).values('identifier').distinct()
                
                speaker_list = []
                for id_dict in identifiers:
                    identifier = id_dict['identifier']
                    speaker_recordings = AudioRecord.objects.filter(
                        category=category,
                        identifier=identifier
                    )
                    
                    recording_count = speaker_recordings.count()
                    
                    # 화자별 대표 정보
                    first_recording = speaker_recordings.first()
                    gender = first_recording.gender if first_recording else 'unknown'
                    diagnosis = first_recording.diagnosis if first_recording and category == 'child' else None
                    
                    # 화자가 diarization된 녹음 수
                    diarized_count = speaker_recordings.exclude(
                        Q(diarization_status__isnull=True) | Q(diarization_status='')
                    ).filter(diarization_status='completed').count()
                    
                    speaker_list.append({
                        'identifier': identifier,
                        'recording_count': recording_count,
                        'gender': gender,
                        'diagnosis': diagnosis,
                        'diarized_count': diarized_count,
                    })
                
                # 녹음 수로 정렬
                speaker_list.sort(key=lambda x: x['recording_count'], reverse=True)
                
                category_stats.append({
                    'category': category,
                    'speaker_count': len(speaker_list),
                    'total_recordings': sum(s['recording_count'] for s in speaker_list),
                    'speakers': speaker_list[:20],  # 상위 20명만
                })
            
            # Context 딕셔너리 생성
            context = {
                'total_speakers': total_speakers,
                'total_files': total_files,
                'category_speakers': category_speakers,
                'category_stats': category_stats,
                'gender_stats': gender_stats,
                'status_stats': status_stats,
                'snr_stats': snr_stats,
                'monthly_stats': monthly_stats,
                'diagnosis_stats': diagnosis_stats,
                'using_cache': True,
                'cache_updated_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            
            # 캐시에 저장
            cache.set(DASHBOARD_CACHE_KEY, context, CACHE_TIMEOUT)
            cache.set(f'{DASHBOARD_CACHE_KEY}_updated_at', context['cache_updated_at'], CACHE_TIMEOUT)
            
            dashboard_elapsed = (timezone.now() - dashboard_start).total_seconds()
            self.stdout.write(self.style.SUCCESS(
                f"✓ 대시보드 캐시 갱신 완료 (소요 시간: {dashboard_elapsed:.2f}초)"
            ))
            self.stdout.write(f"  - 총 화자 수: {total_speakers}")
            self.stdout.write(f"  - 총 파일 수: {total_files}")
            
            # ==================== 위치 정보 통계 ====================
            self.stdout.write("\n[2/2] 위치 정보 통계 데이터 계산 중...")
            userprofile_start = timezone.now()
            
            USERPROFILE_CACHE_KEY = 'userprofile_statistics'
            
            # 기존 캐시 삭제
            cache.delete(USERPROFILE_CACHE_KEY)
            cache.delete(f'{USERPROFILE_CACHE_KEY}_updated_at')
            
            # 지역별 업로드 횟수 집계
            from collections import defaultdict
            upload_locations = defaultdict(int)
            
            # region 필드가 있는 레코드들
            records_with_region = AudioRecord.objects.exclude(region__isnull=True).exclude(region__exact='')
            
            for record in records_with_region:
                region = record.region
                if region:
                    upload_locations[region] += 1
            
            # category_specific_data에서 region 추출
            records_with_category_data = AudioRecord.objects.exclude(category_specific_data__isnull=True)
            
            for record in records_with_category_data:
                category_data = record.category_specific_data or {}
                region = category_data.get('region') or category_data.get('place')
                if region and region not in ['', 'null', None]:
                    upload_locations[region] += 1
            
            # 지역 좌표 매핑
            region_coordinates = {
                '서울': {'lat': 37.5665, 'lng': 126.9780},
                '경기': {'lat': 37.4138, 'lng': 127.5183},
                '인천': {'lat': 37.4563, 'lng': 126.7052},
                '강원': {'lat': 37.8228, 'lng': 128.1555},
                '충북': {'lat': 36.8, 'lng': 127.7},
                '충남': {'lat': 36.5184, 'lng': 126.8000},
                '대전': {'lat': 36.3504, 'lng': 127.3845},
                '전북': {'lat': 35.7175, 'lng': 127.153},
                '전남': {'lat': 34.8679, 'lng': 126.991},
                '광주': {'lat': 35.1595, 'lng': 126.8526},
                '경북': {'lat': 36.4919, 'lng': 128.8889},
                '경남': {'lat': 35.4606, 'lng': 128.2132},
                '대구': {'lat': 35.8714, 'lng': 128.6014},
                '울산': {'lat': 35.5384, 'lng': 129.3114},
                '부산': {'lat': 35.1796, 'lng': 129.0756},
                '제주': {'lat': 33.4996, 'lng': 126.5312},
                '가정': {'lat': 37.5665, 'lng': 126.9780},
                '병원': {'lat': 37.5665, 'lng': 126.9780},
                '센터': {'lat': 37.5665, 'lng': 126.9780},
                '어린이집': {'lat': 37.5665, 'lng': 126.9780},
            }
            
            # 업로드 위치 데이터
            upload_location_data = []
            for region, count in upload_locations.items():
                if region in region_coordinates:
                    upload_location_data.append({
                        'region': region,
                        'count': count,
                        'lat': region_coordinates[region]['lat'],
                        'lng': region_coordinates[region]['lng']
                    })
            
            upload_location_data.sort(key=lambda x: x['count'], reverse=True)
            
            # IP 접근 위치 데이터 (샘플)
            ip_location_data = [
                {'city': '서울', 'count': 150, 'lat': 37.5665, 'lng': 126.9780},
                {'city': '부산', 'count': 45, 'lat': 35.1796, 'lng': 129.0756},
                {'city': '인천', 'count': 32, 'lat': 37.4563, 'lng': 126.7052},
                {'city': '대구', 'count': 28, 'lat': 35.8714, 'lng': 128.6014},
                {'city': '대전', 'count': 22, 'lat': 36.3504, 'lng': 127.3845},
                {'city': '광주', 'count': 18, 'lat': 35.1595, 'lng': 126.8526},
                {'city': '울산', 'count': 12, 'lat': 35.5384, 'lng': 129.3114},
                {'city': '제주', 'count': 8, 'lat': 33.4996, 'lng': 126.5312},
            ]
            
            userprofile_context = {
                'upload_location_data': upload_location_data,
                'ip_location_data': ip_location_data,
                'total_uploads': sum([item['count'] for item in upload_location_data]),
                'total_access': sum([item['count'] for item in ip_location_data]),
                'using_cache': True,
                'cache_updated_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            
            # 캐시에 저장
            cache.set(USERPROFILE_CACHE_KEY, userprofile_context, CACHE_TIMEOUT)
            cache.set(f'{USERPROFILE_CACHE_KEY}_updated_at', userprofile_context['cache_updated_at'], CACHE_TIMEOUT)
            
            userprofile_elapsed = (timezone.now() - userprofile_start).total_seconds()
            self.stdout.write(self.style.SUCCESS(
                f"✓ 위치 정보 캐시 갱신 완료 (소요 시간: {userprofile_elapsed:.2f}초)"
            ))
            self.stdout.write(f"  - 총 업로드 위치: {len(upload_location_data)}개 지역")
            self.stdout.write(f"  - 총 업로드 횟수: {userprofile_context['total_uploads']}")
            
            # 전체 완료 메시지
            end_time = timezone.now()
            total_elapsed = (end_time - start_time).total_seconds()
            
            self.stdout.write(self.style.SUCCESS(
                f"\n✓ 전체 캐시 갱신 완료 (총 소요 시간: {total_elapsed:.2f}초)"
            ))
            self.stdout.write(f"  - 갱신 시각: {context['cache_updated_at']}")
            self.stdout.write(f"  - 캐시 유효 기간: 24시간")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ 캐시 갱신 실패: {str(e)}"))
            raise
