from django.contrib import admin
from .models import AudioRecord

# Register your models here.
@admin.register(AudioRecord)
class AudioRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'audio_file', 'category', 'gender', 'age', 'status', 'created_at')
    list_filter = ('category', 'status', 'gender', 'created_at')
    search_fields = ('audio_file', 'transcription', 'category')
    readonly_fields = ('created_at',)
