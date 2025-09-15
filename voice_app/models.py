from django.db import models
from django.utils import timezone
import json

def category_upload_path(instance, filename):
    """카테고리별로 파일 저장 경로를 결정하는 함수"""
    category = instance.category or 'normal'
    return f'audio/{category}/{filename}'

class AudioRecord(models.Model):
    CATEGORY_CHOICES = [
        ('child', '아동'),
        ('senior', '노인'),
        ('atypical', '음성 장애'),
        ('auditory', '청각 장애'),
        ('normal', '일반'),
    ]
    
    # 공통 필드들 (모든 카테고리에서 사용)
    audio_file = models.FileField(upload_to=category_upload_path)  # 카테고리별 저장
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='normal')
    
    # 공통 기본 정보 (React Native에서 공통으로 사용)
    name = models.CharField(max_length=100, null=True, blank=True, help_text='이름')
    gender = models.CharField(max_length=10, null=True, blank=True, help_text='성별')
    birth_year = models.CharField(max_length=4, null=True, blank=True, help_text='출생년도')
    birth_month = models.CharField(max_length=2, null=True, blank=True, help_text='출생월')
    birth_day = models.CharField(max_length=2, null=True, blank=True, help_text='출생일')
    
    # 공통 녹음 정보
    recording_location = models.CharField(max_length=50, null=True, blank=True, help_text='녹음 장소')
    noise_level = models.CharField(max_length=20, null=True, blank=True, help_text='소음 상태')
    device_type = models.CharField(max_length=30, null=True, blank=True, help_text='녹음 기기')
    has_microphone = models.CharField(max_length=10, null=True, blank=True, help_text='마이크 유무')
    diagnosis = models.CharField(max_length=50, null=True, blank=True, help_text='진단명')
    
    # 카테고리별 특화 데이터를 저장하는 JSON 필드
    category_specific_data = models.JSONField(default=dict, blank=True, help_text='카테고리별 특화 데이터')
    
    # 기존 Django 처리 필드들
    transcription = models.TextField(blank=True, null=True)
    age = models.CharField(max_length=3, null=True, blank=True, help_text='계산된 나이')  # 생년월일에서 계산
    
    # SNR 관련 필드들 (Django에서 처리)
    snr_mean = models.FloatField(null=True, blank=True, help_text='평균 SNR 값')
    snr_max = models.FloatField(null=True, blank=True, help_text='최대 SNR 값')
    snr_min = models.FloatField(null=True, blank=True, help_text='최소 SNR 값')
    
    status = models.CharField(
        max_length=20,
        choices=[('unprocessed', '미전사'), 
                 ('processing', '처리 중'), 
                 ('completed', '전사 완료'), 
                 ('failed', '실패')],
        default='unprocessed'
    )
    
    # WhisperX alignment 관련 필드들
    alignment_data = models.JSONField(null=True, blank=True, help_text='WhisperX alignment 결과 JSON')
    alignment_status = models.CharField(
        max_length=20,
        choices=[('unprocessed', '미처리'), 
                 ('processing', '처리 중'), 
                 ('completed', '완료'), 
                 ('failed', '실패')],
        default='unprocessed'
    )
    
    # 메타 정보
    data_source = models.CharField(
        max_length=20,
        choices=[
            ('mobile_app', '모바일 앱'),
            ('django_admin', 'Django 관리자'),
            ('api_upload', 'API 업로드')
        ],
        default='mobile_app'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """저장 시 나이 자동 계산"""
        if self.birth_year:
            try:
                current_year = timezone.now().year
                birth_year = int(self.birth_year)
                self.age = str(current_year - birth_year)
            except (ValueError, TypeError):
                pass
        super().save(*args, **kwargs)

    # 카테고리별 특화 데이터 접근 메서드들
    def set_category_data(self, **kwargs):
        """카테고리별 데이터 설정"""
        if not self.category_specific_data:
            self.category_specific_data = {}
        self.category_specific_data.update(kwargs)

    def get_category_data(self, key, default=None):
        """카테고리별 데이터 조회"""
        return self.category_specific_data.get(key, default)

    # Child 카테고리 전용 메서드들
    def set_child_data(self, place=None, pronun_problem=None):
        """아동 특화 데이터 설정"""
        child_data = {}
        if place is not None:
            child_data['place'] = place  # 가정, 병원, 센터, 어린이집, 기타
        if pronun_problem is not None:
            child_data['pronun_problem'] = pronun_problem  # 없음, 있음
        
        self.set_category_data(**child_data)

    def get_child_place(self):
        return self.get_category_data('place')
    
    def get_child_pronun_problem(self):
        return self.get_category_data('pronun_problem')

    # Senior 카테고리 전용 메서드들
    def set_senior_data(self, education=None, has_voice_problem=None):
        """노인 특화 데이터 설정"""
        senior_data = {}
        if education is not None:
            senior_data['education'] = education  # 초등학교, 중학교, 고등학교, 대학교, 대학원
        if has_voice_problem is not None:
            senior_data['has_voice_problem'] = has_voice_problem  # 목소리 문제 유무
        
        self.set_category_data(**senior_data)

    def get_senior_education(self):
        return self.get_category_data('education')
    
    def get_senior_voice_problem(self):
        return self.get_category_data('has_voice_problem')

    # Auditory 카테고리 전용 메서드들
    def set_auditory_data(self, education=None, hearing_level=None, hearing_loss_duration=None, 
                         has_hearing_aid=None, cognitive_level=None, region=None, has_voice_problem=None):
        """청각 장애 특화 데이터 설정"""
        auditory_data = {}
        if education is not None:
            auditory_data['education'] = education
        if hearing_level is not None:
            auditory_data['hearing_level'] = hearing_level  # 정상, 경도난청, 중도난청 등
        if hearing_loss_duration is not None:
            auditory_data['hearing_loss_duration'] = hearing_loss_duration  # 선천성, 1년 미만 등
        if has_hearing_aid is not None:
            auditory_data['has_hearing_aid'] = has_hearing_aid
        if cognitive_level is not None:
            auditory_data['cognitive_level'] = cognitive_level  # 정상, 경도인지장애 등
        if region is not None:
            auditory_data['region'] = region  # 서울, 경기 등
        if has_voice_problem is not None:
            auditory_data['has_voice_problem'] = has_voice_problem
        
        self.set_category_data(**auditory_data)

    def get_auditory_hearing_level(self):
        return self.get_category_data('hearing_level')
    
    def get_auditory_cognitive_level(self):
        return self.get_category_data('cognitive_level')
    
    def get_auditory_region(self):
        return self.get_category_data('region')

    @property
    def category_fields_schema(self):
        """카테고리별 필드 스키마 정의 (프론트엔드 참조용)"""
        schemas = {
            'child': {
                'place': {
                    'label': '녹음 장소',
                    'type': 'choice',
                    'choices': ['가정', '병원', '센터', '어린이집', '기타']
                },
                'pronun_problem': {
                    'label': '발음 문제',
                    'type': 'choice', 
                    'choices': ['없음', '있음']
                }
            },
            'senior': {
                'education': {
                    'label': '교육 수준',
                    'type': 'choice',
                    'choices': ['초등학교', '중학교', '고등학교', '대학교', '대학원']
                },
                'has_voice_problem': {
                    'label': '목소리 문제',
                    'type': 'choice',
                    'choices': ['없음', '있음']
                }
            },
            'auditory': {
                'education': {
                    'label': '교육 수준',
                    'type': 'choice',
                    'choices': ['초등학교', '중학교', '고등학교', '대학교', '대학원']
                },
                'hearing_level': {
                    'label': '청력 수준',
                    'type': 'choice',
                    'choices': ['정상', '경도난청', '중도난청', '중고도난청', '고도난청', '심도난청']
                },
                'hearing_loss_duration': {
                    'label': '난청 지속 기간',
                    'type': 'choice',
                    'choices': ['선천성', '1년 미만', '1-5년', '5-10년', '10년 이상']
                },
                'has_hearing_aid': {
                    'label': '보청기 사용',
                    'type': 'choice',
                    'choices': ['없음', '있음']
                },
                'cognitive_level': {
                    'label': '인지 수준',
                    'type': 'choice',
                    'choices': ['정상', '경도인지장애', '중등도인지장애', '중도인지장애']
                },
                'region': {
                    'label': '지역',
                    'type': 'choice',
                    'choices': ['서울', '경기', '인천', '강원', '충북', '충남', '대전', '전북', '전남', '광주', '경북', '경남', '대구', '울산', '부산', '제주']
                },
                'has_voice_problem': {
                    'label': '목소리 문제',
                    'type': 'choice',
                    'choices': ['없음', '있음']
                }
            }
        }
        return schemas.get(self.category, {})

    def get_formatted_metadata(self):
        """포맷된 메타데이터 반환"""
        metadata = {}
        
        # 기본 정보
        if self.name:
            metadata['이름'] = self.name
        if self.gender:
            metadata['성별'] = self.gender
        if self.age:
            metadata['나이'] = f"{self.age}세"
        
        # 생년월일
        if self.birth_year and self.birth_month and self.birth_day:
            metadata['생년월일'] = f"{self.birth_year}년 {self.birth_month}월 {self.birth_day}일"
        
        # 녹음 환경
        if self.recording_location:
            metadata['녹음 장소'] = self.recording_location
        if self.noise_level:
            metadata['소음 수준'] = self.noise_level
        if self.device_type:
            metadata['기기 유형'] = self.device_type
        if self.has_microphone:
            metadata['마이크 사용'] = self.has_microphone
        
        # SNR 정보
        if self.snr_mean is not None:
            metadata['SNR 평균'] = f"{self.snr_mean:.2f} dB"
        if self.snr_max is not None:
            metadata['SNR 최대'] = f"{self.snr_max:.2f} dB"
        if self.snr_min is not None:
            metadata['SNR 최소'] = f"{self.snr_min:.2f} dB"
        
        return metadata

    def get_formatted_category_data(self):
        """포맷된 카테고리별 데이터 반환"""
        if not self.category_specific_data:
            return {}
        
        schema_map = {
            'child': {
                'place': '녹음 장소',
                'pronunciation_problem': '발음 문제',
                'region': '지역',
                'sentence_index': '문장 번호',
                'sentence_text': '문장 내용',
                'task_type': '과제 유형'
            },
            'senior': {
                'education': '교육 수준',
                'has_voice_problem': '음성 문제 여부',
                'region': '지역'
            },
            'auditory': {
                'education': '교육 수준',
                'hearing_level': '청력 수준',
                'hearing_loss_duration': '청력 손실 기간',
                'has_hearing_aid': '보청기 착용',
                'cognitive_level': '인지 수준',
                'region': '지역',
                'has_voice_problem': '음성 문제 여부'
            }
        }
        
        schema = schema_map.get(self.category, {})
        formatted_data = {}
        
        for key, value in self.category_specific_data.items():
            display_name = schema.get(key, key)
            if value:
                formatted_data[display_name] = value
        
        return formatted_data

    def __str__(self):
        return f"{self.get_category_display()} - {self.name or 'Unknown'} - {self.audio_file.name}"

    class Meta:
        verbose_name = '음성 레코드'
        verbose_name_plural = '음성 레코드들'
        ordering = ['-created_at']
