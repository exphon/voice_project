from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import AudioUploadView, SimpleCategoryUploadView
from .views import audio_list, delete_all_audios, category_audio_list, audio_detail, dashboard, userprofile
from .views import update_transcription, update_audio_metadata
from .views import transcribe_unprocessed
from .views import api_all_audio_list, api_audio_detail, api_participant_metadata, api_category_participant_metadata
from .views import whisperx_transcribe, whisperx_transcribe_simple
from .views import whisperx_align_audio, get_alignment_data, get_alignment_status
from .views import api_child_info, api_status, api_config, test_file_upload
from .views import audio_download, audio_reupload  # 새로 추가

# app_name = 'voice_app'  # namespace 제거

urlpatterns = [
    path('', views.index, name='index'),  # ✅ 루트 경로에 index.html 연결
    
    # 프로필 및 대시보드
    path('userprofile/', userprofile, name='userprofile'),
    path('dashboard/', dashboard, name='dashboard'),
    
    # Assets 파일 목록 API (React Native용) - 먼저 배치
    path('assets/list/', views.api_assets_list, name='api_assets_list'),
    path('assets/list/<str:category>/<str:folder>/', views.api_assets_files, name='api_assets_files'),
    
    # REST API 업로드 엔드포인트
    path('<str:category>/upload/', AudioUploadView.as_view(), name='api_category_audio_upload'),
    
    # 누락된 API 엔드포인트들 추가
    path('child/info/', views.api_child_info, name='api_child_info'),
    
    # 참가자 메타데이터 API - 여러 URL 형식 지원
    path('participant/<str:identifier>/', api_participant_metadata, name='api_participant_metadata'),  # 범용 (모든 카테고리)
    path('child/participant/<str:identifier>/', api_category_participant_metadata, {'category': 'child'}, name='api_child_participant'),  # child 전용
    path('senior/participant/<str:identifier>/', api_category_participant_metadata, {'category': 'senior'}, name='api_senior_participant'),  # senior 전용
    path('auditory/participant/<str:identifier>/', api_category_participant_metadata, {'category': 'auditory'}, name='api_auditory_participant'),  # auditory 전용
    path('atypical/participant/<str:identifier>/', api_category_participant_metadata, {'category': 'atypical'}, name='api_atypical_participant'),  # atypical 전용
    path('normal/participant/<str:identifier>/', api_category_participant_metadata, {'category': 'normal'}, name='api_normal_participant'),  # normal 전용
    
    path('status/', views.api_status, name='api_status'),
    path('config/', views.api_config, name='api_config'),
    path('test-upload/', views.test_file_upload, name='api_test_upload'),  # React Native 테스트용
    
    # 웹 인터페이스 URL들
    path('list/', views.audio_list, name='audio_list'),
    path('dashboard/', dashboard, name='dashboard'),
    path('audio/<int:audio_id>/', audio_detail, name='audio_detail'),
    path('<str:category>/list/', category_audio_list, name='category_audio_list'),
    
    # 오디오 파일 다운로드 및 재업로드
    path('audio/<int:audio_id>/download/', audio_download, name='audio_download'),
    path('audio/<int:audio_id>/reupload/', audio_reupload, name='audio_reupload'),
    
    # React Native API URL들 (JSON 응답)
    path('<str:category>/list/api/', SimpleCategoryUploadView.as_view(), name='api_category_audio_list'),
    path('<str:category>/upload/api/', SimpleCategoryUploadView.as_view(), name='api_category_upload'),  # 카테고리별 업로드 API
    path('all/list/api/', api_all_audio_list, name='api_all_audio_list'),
    path('audio/<int:audio_id>/api/', api_audio_detail, name='api_audio_detail'),
    
    # 업로드 URL들
    path('upload/', AudioUploadView.as_view(), name='audio-upload'),
    path('<str:category>/upload/', AudioUploadView.as_view(), name='category-audio-upload'),
    path('django-upload/', views.django_upload, name='django_upload'),
    
    # 기타 기능들
    path('reset_processing/', views.reset_processing_status, name='reset_processing_status'),
    path('delete_all/', delete_all_audios, name='delete_all_audios'),
    path('update/<int:audio_id>/', update_transcription, name='update_transcription'),
    path('update-metadata/<int:audio_id>/', update_audio_metadata, name='update_audio_metadata'),
    path('transcribe/', transcribe_unprocessed, name='transcribe_unprocessed'),
    path('transcribe/<int:audio_id>/', views.transcribe_single_audio, name='transcribe_single_audio'),
    
    # WhisperX API 엔드포인트
    path('whisperx/transcribe/', whisperx_transcribe, name='whisperx_transcribe'),
    path('whisperx/transcribe/simple/', whisperx_transcribe_simple, name='whisperx_transcribe_simple'),
    
    # WhisperX Alignment 관련 URL들
    path('align/<int:audio_id>/', whisperx_align_audio, name='whisperx_align_audio'),
    path('alignment-data/<int:audio_id>/', get_alignment_data, name='get_alignment_data'),
    path('alignment-status/<int:audio_id>/', get_alignment_status, name='get_alignment_status'),
    
    # 기존 패턴들
    path('audio_list/', views.audio_list, name='audio_list'),
    path('audio/<int:audio_id>/', views.audio_detail, name='audio_detail'),
    path('update_transcription/<int:audio_id>/', views.update_transcription, name='update_transcription'),
    path('update_audio_metadata/<int:audio_id>/', views.update_audio_metadata, name='update_audio_metadata'),
    
    # 새로 추가할 패턴
    path('update_category_data/<int:audio_id>/', views.update_category_data, name='update_category_data'),
    
    # API 관련 패턴들도 추가
    path('alignment-status/<int:audio_id>/', views.alignment_status_api, name='alignment_status_api'),
    path('alignment-data/<int:audio_id>/', views.alignment_data_api, name='alignment_data_api'),
    
    # 고유 ID 필터링
    path('identifier/<str:identifier>/', views.identifier_audio_list, name='identifier_audio_list'),
]
