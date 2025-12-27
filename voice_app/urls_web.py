from django.urls import path
from . import views
from .views import AudioUploadView

app_name = 'voice_app'

urlpatterns = [
    # Web UI
    path('', views.index, name='index'),
    path('userprofile/', views.userprofile, name='userprofile'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Lists / detail
    path('list/', views.audio_list, name='audio_list'),
    path('audio/<int:audio_id>/', views.audio_detail, name='audio_detail'),
    path('<str:category>/list/', views.category_audio_list, name='category_audio_list'),
    path('identifier/<str:identifier>/', views.identifier_audio_list, name='identifier_audio_list'),

    # File actions
    path('audio/<int:audio_id>/download/', views.audio_download, name='audio_download'),
    path('audio/<int:audio_id>/reupload/', views.audio_reupload, name='audio_reupload'),
    path('audio/<int:audio_id>/delete/', views.audio_delete, name='audio_delete'),

    # Upload (web or shared)
    path('upload/', AudioUploadView.as_view(), name='audio-upload'),
    path('<str:category>/upload/', AudioUploadView.as_view(), name='category-audio-upload'),
    path('django-upload/', views.django_upload, name='django_upload'),

    # Updates
    path('update/<int:audio_id>/', views.update_transcription, name='update_transcription'),
    path('update-memo/<int:audio_id>/', views.update_memo, name='update_memo'),
    path('update-metadata/<int:audio_id>/', views.update_audio_metadata, name='update_audio_metadata'),
    path('update_category_data/<int:audio_id>/', views.update_category_data, name='update_category_data'),

    # Batch / processing
    path('reset_processing/', views.reset_processing_status, name='reset_processing_status'),
    path('delete_all/', views.delete_all_audios, name='delete_all_audios'),
    path('transcribe/', views.transcribe_unprocessed, name='transcribe_unprocessed'),
    path('<str:category>/transcribe/', views.transcribe_unprocessed_category, name='transcribe_unprocessed_category'),
    path('transcribe/<int:audio_id>/', views.transcribe_single_audio, name='transcribe_single_audio'),

    # Alignment / diarization (used by web UI via JS)
    path('align/<int:audio_id>/', views.whisperx_align_audio, name='whisperx_align_audio'),
    path('alignment-data/<int:audio_id>/', views.get_alignment_data, name='get_alignment_data'),
    path('alignment-status/<int:audio_id>/', views.get_alignment_status, name='get_alignment_status'),
    path('diarize/<int:audio_id>/', views.perform_diarization, name='perform_diarization'),
    path('diarization-data/<int:audio_id>/', views.get_diarization_data, name='get_diarization_data'),
    path('diarization-status/<int:audio_id>/', views.get_diarization_status, name='get_diarization_status'),
    path('extract-speaker/<int:audio_id>/', views.extract_speaker_audio, name='extract_speaker_audio'),
]
