from django.urls import path
from . import views
from .views import AudioUploadView, SimpleCategoryUploadView

app_name = 'voice_app_api'

urlpatterns = [
    # Assets (React Native)
    path('assets/list/', views.api_assets_list, name='api_assets_list'),
    path('assets/list/<str:category>/<str:folder>/', views.api_assets_files, name='api_assets_files'),

    # Upload APIs
    path('<str:category>/upload/', AudioUploadView.as_view(), name='api_category_audio_upload'),
    path('<str:category>/upload/api/', SimpleCategoryUploadView.as_view(), name='api_category_upload'),

    # Lists / detail APIs
    path('<str:category>/list/', views.category_audio_list, name='category_audio_list'),
    path('<str:category>/list/api/', SimpleCategoryUploadView.as_view(), name='api_category_audio_list'),
    path('all/list/api/', views.api_all_audio_list, name='api_all_audio_list'),
    path('audio/<int:audio_id>/api/', views.api_audio_detail, name='api_audio_detail'),

    # Participant metadata APIs
    path('participant/<str:identifier>/', views.api_participant_metadata, name='api_participant_metadata'),
    path('child/participant/<str:identifier>/', views.api_category_participant_metadata, {'category': 'child'}, name='api_child_participant'),
    path('senior/participant/<str:identifier>/', views.api_category_participant_metadata, {'category': 'senior'}, name='api_senior_participant'),
    path('auditory/participant/<str:identifier>/', views.api_category_participant_metadata, {'category': 'auditory'}, name='api_auditory_participant'),
    path('atypical/participant/<str:identifier>/', views.api_category_participant_metadata, {'category': 'atypical'}, name='api_atypical_participant'),
    path('normal/participant/<str:identifier>/', views.api_category_participant_metadata, {'category': 'normal'}, name='api_normal_participant'),

    # Status/config/test
    path('child/info/', views.api_child_info, name='api_child_info'),
    path('status/', views.api_status, name='api_status'),
    path('config/', views.api_config, name='api_config'),
    path('test-upload/', views.test_file_upload, name='api_test_upload'),

    # WhisperX APIs
    path('whisperx/transcribe/', views.whisperx_transcribe, name='whisperx_transcribe'),
    path('whisperx/transcribe/simple/', views.whisperx_transcribe_simple, name='whisperx_transcribe_simple'),

    # Alignment / diarization APIs
    path('align/<int:audio_id>/', views.whisperx_align_audio, name='whisperx_align_audio'),
    path('alignment-data/<int:audio_id>/', views.get_alignment_data, name='get_alignment_data'),
    path('alignment-status/<int:audio_id>/', views.get_alignment_status, name='get_alignment_status'),
    path('diarize/<int:audio_id>/', views.perform_diarization, name='perform_diarization'),
    path('diarization-data/<int:audio_id>/', views.get_diarization_data, name='get_diarization_data'),
    path('diarization-status/<int:audio_id>/', views.get_diarization_status, name='get_diarization_status'),
    path('extract-speaker/<int:audio_id>/', views.extract_speaker_audio, name='extract_speaker_audio'),
]
