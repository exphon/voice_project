from django.conf import settings
from django.db import models
from django.utils import timezone

from voice_app.models import AudioRecord


class VoiceAnalysis(models.Model):
    ANALYSIS_TYPE_CHOICES = [
        ("basic", "기본 분석"),
        ("snr", "SNR 분석"),
        ("alignment", "정렬 분석"),
        ("diarization", "화자 분리 분석"),
        ("ddk", "DDK 분석"),
        ("vowel_marker", "모음 마커"),
        ("custom", "사용자 정의 분석"),
    ]

    STATUS_CHOICES = [
        ("pending", "대기 중"),
        ("processing", "처리 중"),
        ("completed", "완료"),
        ("failed", "실패"),
    ]

    audio_record = models.ForeignKey(
        AudioRecord,
        on_delete=models.CASCADE,
        related_name="voice_analyses",
        help_text="분석 대상 음성 레코드",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voice_analyses",
        help_text="분석을 요청한 사용자",
    )
    analysis_type = models.CharField(
        max_length=20,
        choices=ANALYSIS_TYPE_CHOICES,
        default="basic",
        help_text="분석 유형",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        help_text="분석 진행 상태",
    )
    input_snapshot = models.JSONField(default=dict, blank=True, help_text="분석 시점 입력 데이터 스냅샷")
    result_data = models.JSONField(default=dict, blank=True, help_text="분석 결과 JSON")
    summary = models.TextField(blank=True, help_text="분석 요약")
    error_message = models.TextField(blank=True, help_text="분석 실패 메시지")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Voice analysis"
        verbose_name_plural = "Voice analyses"
        indexes = [
            models.Index(fields=["analysis_type", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.audio_record_id}:{self.analysis_type}:{self.status}"

    def mark_processing(self):
        self.status = "processing"
        if self.started_at is None:
            self.started_at = timezone.now()

    def mark_completed(self, result_data=None, summary=""):
        self.status = "completed"
        self.completed_at = timezone.now()
        self.error_message = ""
        if result_data is not None:
            self.result_data = result_data
        if summary:
            self.summary = summary

    def mark_failed(self, message):
        self.status = "failed"
        self.completed_at = timezone.now()
        self.error_message = message