from django.contrib import admin

from .models import VoiceAnalysis


@admin.register(VoiceAnalysis)
class VoiceAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "audio_record",
        "analysis_type",
        "status",
        "requested_by",
        "created_at",
        "completed_at",
    )
    list_filter = ("analysis_type", "status", "created_at")
    search_fields = (
        "audio_record__identifier",
        "audio_record__audio_file",
        "summary",
        "error_message",
    )
    readonly_fields = ("created_at", "updated_at", "started_at", "completed_at")