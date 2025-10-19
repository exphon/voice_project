from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
import json

def category_upload_path(instance, filename):
    """카테고리별로 파일 저장 경로를 결정하는 함수"""
    category = instance.category or 'normal'
    return f'audio/{category}/{filename}'

class AudioRecord(models.Model):
    identifier_validator = RegexValidator(
        regex=r'^[CSA]\d{5}$',
        message='Identifier는 C, S, 혹은 A로 시작하고 5자리 숫자가 뒤따라야 합니다.'
    )

    CATEGORY_CHOICES = [
        ('child', '아동'),
        ('senior', '성인'),
        ('atypical', '음성 장애'),
        ('auditory', '청각 장애'),
        ('normal', '일반'),
    ]
    
    # 공통 필드들 (모든 카테고리에서 사용)
    audio_file = models.FileField(upload_to=category_upload_path)  # 카테고리별 저장
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='normal')
    identifier = models.CharField(
        max_length=6,
        null=True,
        blank=True,
        validators=[identifier_validator],
        help_text='C, S, 혹은 A로 시작하고 5자리 숫자로 구성된 식별자'
    )
    
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
    diagnosis = models.CharField(max_length=100, null=True, blank=True, help_text='진단명')
    region = models.CharField(max_length=20, null=True, blank=True, help_text='거주 지역', db_index=True)
    
    # 자주 쿼리되는 카테고리별 핵심 필드 (성능 최적화용)
    education_level = models.IntegerField(null=True, blank=True, help_text='총 교육년수 (Senior/Auditory)', db_index=True)
    hearing_level = models.CharField(max_length=30, null=True, blank=True, help_text='청력 수준 (Auditory)', db_index=True)
    age_in_months = models.IntegerField(null=True, blank=True, help_text='나이(개월) (Child/Auditory)')
    
    # 카테고리별 특화 데이터를 저장하는 JSON 필드
    category_specific_data = models.JSONField(default=dict, blank=True, help_text='카테고리별 특화 데이터')
    
    # 기존 Django 처리 필드들
    transcript = models.TextField(blank=True, null=True, help_text='Whisper 자동 전사 결과')
    manual_transcript = models.TextField(blank=True, null=True, help_text='수동 수정된 전사 내용')
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
    def set_child_data(self, place=None, pronun_problem=None, age_in_months=None, 
                      subjective_rating=None, **kwargs):
        """아동 특화 데이터 설정"""
        child_data = {}
        if place is not None:
            child_data['place'] = place  # 가정, 병원, 센터, 어린이집, 기타
        if pronun_problem is not None:
            child_data['pronunciation_problem'] = pronun_problem  # 없음, 있음
        if age_in_months is not None:
            child_data['age_in_months'] = age_in_months  # 개월 수
        if subjective_rating is not None:
            child_data['subjective_rating'] = subjective_rating  # 주관적 평가
        
        # 추가 필드
        child_data.update(kwargs)
        
        self.set_category_data(**child_data)

    def get_child_place(self):
        return self.get_category_data('place')
    
    def get_child_pronun_problem(self):
        return self.get_category_data('pronunciation_problem')
    
    def get_child_age_in_months(self):
        return self.get_category_data('age_in_months')
    
    def get_child_subjective_rating(self):
        return self.get_category_data('subjective_rating')

    # Senior 카테고리 전용 메서드들
    def set_senior_data(self, education=None, education_years=None, final_education=None,
                       education_detail=None, has_voice_problem=None, cognitive_decline=None,
                       subjective_score=None, subjective_note=None, job=None, **kwargs):
        """성인 특화 데이터 설정"""
        senior_data = {}
        if education is not None:
            senior_data['education'] = education  # 무학, 초등학교, 중학교, 고등학교, 대학교, 대학원
        if education_years is not None:
            senior_data['education_years'] = education_years  # 해당 학교 교육 년수
        if final_education is not None:
            senior_data['final_education'] = final_education  # 총 교육년수
        if education_detail is not None:
            senior_data['education_detail'] = education_detail  # 교육 상세
        if has_voice_problem is not None:
            senior_data['has_voice_problem'] = has_voice_problem  # 목소리 문제 유무
        if cognitive_decline is not None:
            senior_data['cognitive_decline'] = cognitive_decline  # 인지 저하
        if subjective_score is not None:
            senior_data['subjective_score'] = subjective_score  # 주관적 평가 점수
        if subjective_note is not None:
            senior_data['subjective_note'] = subjective_note  # 주관적 평가 메모
        if job is not None:
            senior_data['job'] = job  # 직업
        
        # 추가 필드
        senior_data.update(kwargs)
        
        self.set_category_data(**senior_data)

    def get_senior_education(self):
        return self.get_category_data('education')
    
    def get_senior_education_years(self):
        return self.get_category_data('education_years')
    
    def get_senior_final_education(self):
        return self.get_category_data('final_education')
    
    def get_senior_education_detail(self):
        return self.get_category_data('education_detail')
    
    def get_senior_voice_problem(self):
        return self.get_category_data('has_voice_problem')
    
    def get_senior_cognitive_decline(self):
        return self.get_category_data('cognitive_decline')
    
    def get_senior_subjective_score(self):
        return self.get_category_data('subjective_score')
    
    def get_senior_subjective_note(self):
        return self.get_category_data('subjective_note')
    
    def get_senior_job(self):
        return self.get_category_data('job')

    # Auditory 카테고리 전용 메서드들
    def set_auditory_data(self, education=None, education_detail=None, final_education=None,
                         birth_date=None, recording_date=None, 
                         hearing_onset_type=None, hearing_degree=None, hearing_level=None, 
                         hearing_loss_duration=None, hearing_impairment=None,
                         has_hearing_aid=None, hearing_aid_duration=None, 
                         cognitive_level=None, region=None, 
                         has_voice_problem=None, voice_problem_severity=None, voice_problem_note=None,
                         native_language=None, language_experience=None,
                         session_id=None, background_noise_average=None, background_noise_max=None,
                         background_noise_min=None, noise_measurement_time=None, platform=None,
                         age_in_months=None, attempts=None, **kwargs):
        """청각 장애 특화 데이터 설정 (완전 확장)"""
        auditory_data = {}
        
        # 교육 정보
        if education is not None:
            auditory_data['education'] = education
        if education_detail is not None:
            auditory_data['education_detail'] = education_detail
        if final_education is not None:
            auditory_data['final_education'] = final_education
        if birth_date is not None:
            auditory_data['birth_date'] = birth_date
        if recording_date is not None:
            auditory_data['recording_date'] = recording_date
            
        # 청각 관련 정보
        if hearing_onset_type is not None:
            auditory_data['hearing_onset_type'] = hearing_onset_type  # 선천성, 후천성
        if hearing_degree is not None:
            auditory_data['hearing_degree'] = hearing_degree
        if hearing_level is not None:
            auditory_data['hearing_level'] = hearing_level  # 정상, 경도난청, 중도난청, 중고도난청, 고도난청, 심도난청
        if hearing_loss_duration is not None:
            auditory_data['hearing_loss_duration'] = hearing_loss_duration  # 없음, 선천성, 1년 미만, 1-5년, 5-10년, 10년 이상
        if hearing_impairment is not None:
            auditory_data['hearing_impairment'] = hearing_impairment
            
        # 보청기 정보
        if has_hearing_aid is not None:
            auditory_data['has_hearing_aid'] = has_hearing_aid  # 예, 아니오
        if hearing_aid_duration is not None:
            auditory_data['hearing_aid_duration'] = hearing_aid_duration
            
        # 인지 관련
        if cognitive_level is not None:
            auditory_data['cognitive_level'] = cognitive_level  # 정상, 경도인지장애, 중등도인지장애, 중도인지장애
            
        # 지역
        if region is not None:
            auditory_data['region'] = region  # 서울, 경기, 인천, 강원, 충북, 충남, 대전, 전북, 전남, 광주, 경북, 경남, 대구, 울산, 부산, 제주
            
        # 음성 문제 관련
        if has_voice_problem is not None:
            auditory_data['has_voice_problem'] = has_voice_problem
        if voice_problem_severity is not None:
            auditory_data['voice_problem_severity'] = voice_problem_severity
        if voice_problem_note is not None:
            auditory_data['voice_problem_note'] = voice_problem_note
        
        # 언어 관련
        if native_language is not None:
            auditory_data['native_language'] = native_language
        if language_experience is not None:
            auditory_data['language_experience'] = language_experience
        
        # 배경소음 측정
        if session_id is not None:
            auditory_data['session_id'] = session_id
        if background_noise_average is not None:
            auditory_data['background_noise_average'] = background_noise_average
        if background_noise_max is not None:
            auditory_data['background_noise_max'] = background_noise_max
        if background_noise_min is not None:
            auditory_data['background_noise_min'] = background_noise_min
        if noise_measurement_time is not None:
            auditory_data['noise_measurement_time'] = noise_measurement_time
        if platform is not None:
            auditory_data['platform'] = platform  # iOS/Android
        
        # 나이 (개월)
        if age_in_months is not None:
            auditory_data['age_in_months'] = age_in_months
            
        # 시도 정보 (JSON 문자열)
        if attempts is not None:
            auditory_data['attempts'] = attempts
            
        # 추가 필드들
        auditory_data.update(kwargs)
        
        self.set_category_data(**auditory_data)

    # Auditory 접근 메서드 - 교육
    def get_auditory_education(self):
        return self.get_category_data('education')
    
    def get_auditory_education_detail(self):
        return self.get_category_data('education_detail')
    
    def get_auditory_final_education(self):
        return self.get_category_data('final_education')
    
    # Auditory 접근 메서드 - 청각
    def get_auditory_hearing_level(self):
        return self.get_category_data('hearing_level')
    
    def get_auditory_hearing_onset_type(self):
        return self.get_category_data('hearing_onset_type')
    
    def get_auditory_hearing_loss_duration(self):
        return self.get_category_data('hearing_loss_duration')
    
    def get_auditory_hearing_impairment(self):
        return self.get_category_data('hearing_impairment')
    
    def get_auditory_has_hearing_aid(self):
        return self.get_category_data('has_hearing_aid')
    
    def get_auditory_hearing_aid_duration(self):
        return self.get_category_data('hearing_aid_duration')
    
    # Auditory 접근 메서드 - 인지
    def get_auditory_cognitive_level(self):
        return self.get_category_data('cognitive_level')
    
    # Auditory 접근 메서드 - 지역 및 음성
    def get_auditory_region(self):
        return self.get_category_data('region')
    
    def get_auditory_voice_problem_severity(self):
        return self.get_category_data('voice_problem_severity')
    
    def get_auditory_voice_problem_note(self):
        return self.get_category_data('voice_problem_note')
    
    # Auditory 접근 메서드 - 언어
    def get_auditory_native_language(self):
        return self.get_category_data('native_language')
    
    def get_auditory_language_experience(self):
        return self.get_category_data('language_experience')
    
    # Auditory 접근 메서드 - 배경소음
    def get_auditory_session_id(self):
        return self.get_category_data('session_id')
    
    def get_auditory_background_noise_average(self):
        return self.get_category_data('background_noise_average')
    
    def get_auditory_background_noise_max(self):
        return self.get_category_data('background_noise_max')
    
    def get_auditory_background_noise_min(self):
        return self.get_category_data('background_noise_min')
    
    def get_auditory_noise_measurement_time(self):
        return self.get_category_data('noise_measurement_time')
    
    def get_auditory_platform(self):
        return self.get_category_data('platform')
    
    def get_auditory_age_in_months(self):
        return self.get_category_data('age_in_months')
    
    def get_auditory_attempts(self):
        """시도 정보 반환 (JSON 문자열 또는 딕셔너리)"""
        return self.get_category_data('attempts')

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
                'pronunciation_problem': {
                    'label': '발음 문제',
                    'type': 'choice', 
                    'choices': ['없음', '있음']
                },
                'age_in_months': {
                    'label': '나이 (개월)',
                    'type': 'number'
                },
                'subjective_rating': {
                    'label': '주관적 평가',
                    'type': 'number'
                }
            },
            'senior': {
                'education': {
                    'label': '학교 선택',
                    'type': 'choice',
                    'choices': ['무학', '초등학교', '중학교', '고등학교', '대학교', '대학원(석사)', '대학원(박사)']
                },
                'education_years': {
                    'label': '교육 년수',
                    'type': 'number'
                },
                'final_education': {
                    'label': '총 교육년수',
                    'type': 'number'
                },
                'education_detail': {
                    'label': '교육 상세',
                    'type': 'text'
                },
                'has_voice_problem': {
                    'label': '목소리 문제',
                    'type': 'choice',
                    'choices': ['없음', '있음']
                },
                'cognitive_decline': {
                    'label': '인지 저하',
                    'type': 'text'
                },
                'subjective_score': {
                    'label': '주관적 평가 점수',
                    'type': 'number'
                },
                'subjective_note': {
                    'label': '주관적 평가 메모',
                    'type': 'text'
                },
                'job': {
                    'label': '직업',
                    'type': 'text'
                }
            },
            'auditory': {
                'education': {
                    'label': '교육 수준',
                    'type': 'choice',
                    'choices': ['초등학교', '중학교', '고등학교', '대학교', '대학원']
                },
                'education_detail': {
                    'label': '교육 상세',
                    'type': 'text'
                },
                'final_education': {
                    'label': '총 교육년수',
                    'type': 'number'
                },
                'birth_date': {
                    'label': '생년월일',
                    'type': 'date'
                },
                'recording_date': {
                    'label': '녹음일',
                    'type': 'date'
                },
                'hearing_onset_type': {
                    'label': '청력 손실 발생 시기',
                    'type': 'choice',
                    'choices': ['선천성', '후천성']
                },
                'hearing_level': {
                    'label': '청력 수준',
                    'type': 'choice',
                    'choices': ['정상', '경도난청', '중도난청', '중고도난청', '고도난청', '심도난청']
                },
                'hearing_loss_duration': {
                    'label': '난청 기간',
                    'type': 'choice',
                    'choices': ['없음', '선천성', '1년 미만', '1-5년', '5-10년', '10년 이상']
                },
                'hearing_impairment': {
                    'label': '청각 장애',
                    'type': 'text'
                },
                'has_hearing_aid': {
                    'label': '보청기 착용',
                    'type': 'choice',
                    'choices': ['예', '아니오']
                },
                'hearing_aid_duration': {
                    'label': '보청기 사용 기간',
                    'type': 'text'
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
                },
                'voice_problem_severity': {
                    'label': '목소리 문제 심각도',
                    'type': 'number'
                },
                'voice_problem_note': {
                    'label': '목소리 문제 메모',
                    'type': 'text'
                },
                'native_language': {
                    'label': '모국어',
                    'type': 'text'
                },
                'language_experience': {
                    'label': '언어 경험',
                    'type': 'text'
                },
                'session_id': {
                    'label': '세션 ID',
                    'type': 'text'
                },
                'background_noise_average': {
                    'label': '평균 배경소음',
                    'type': 'number'
                },
                'background_noise_max': {
                    'label': '최대 배경소음',
                    'type': 'number'
                },
                'background_noise_min': {
                    'label': '최소 배경소음',
                    'type': 'number'
                },
                'noise_measurement_time': {
                    'label': '소음 측정 시간',
                    'type': 'text'
                },
                'platform': {
                    'label': '플랫폼',
                    'type': 'choice',
                    'choices': ['iOS', 'Android']
                },
                'age_in_months': {
                    'label': '나이 (개월)',
                    'type': 'number'
                },
                'attempts': {
                    'label': '시도 정보',
                    'type': 'json'
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
        if self.identifier:
            metadata['식별자'] = self.identifier
        
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
                'education_detail': '교육 상세',
                'birth_date': '생년월일',
                'recording_date': '녹음일',
                'hearing_onset_type': '청력 손실 발생 시기',
                'hearing_degree': '청력 손실 정도',
                'hearing_level': '청력 수준',
                'hearing_loss_duration': '청력 손실 기간',
                'has_hearing_aid': '보청기 착용',
                'hearing_aid_duration': '보청기 사용 기간',
                'cognitive_level': '인지 수준',
                'region': '지역',
                'has_voice_problem': '음성 문제 여부',
                'voice_problem_severity': '음성 문제 심각도',
                'voice_problem_note': '음성 문제 메모',
                'attempts': '시도 정보'
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
        identifier_part = f"{self.identifier} - " if self.identifier else ''
        return f"{identifier_part}{self.get_category_display()} - {self.name or 'Unknown'} - {self.audio_file.name}"

    class Meta:
        verbose_name = '음성 레코드'
        verbose_name_plural = '음성 레코드들'
        ordering = ['-created_at']
