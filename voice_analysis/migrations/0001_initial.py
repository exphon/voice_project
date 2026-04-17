from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("voice_app", "0017_audiorecord_memo"),
    ]

    operations = [
        migrations.CreateModel(
            name="VoiceAnalysis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("analysis_type", models.CharField(choices=[("basic", "기본 분석"), ("snr", "SNR 분석"), ("alignment", "정렬 분석"), ("diarization", "화자 분리 분석"), ("custom", "사용자 정의 분석")], default="basic", help_text="분석 유형", max_length=20)),
                ("status", models.CharField(choices=[("pending", "대기 중"), ("processing", "처리 중"), ("completed", "완료"), ("failed", "실패")], default="pending", help_text="분석 진행 상태", max_length=20)),
                ("input_snapshot", models.JSONField(blank=True, default=dict, help_text="분석 시점 입력 데이터 스냅샷")),
                ("result_data", models.JSONField(blank=True, default=dict, help_text="분석 결과 JSON")),
                ("summary", models.TextField(blank=True, help_text="분석 요약")),
                ("error_message", models.TextField(blank=True, help_text="분석 실패 메시지")),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("audio_record", models.ForeignKey(help_text="분석 대상 음성 레코드", on_delete=django.db.models.deletion.CASCADE, related_name="voice_analyses", to="voice_app.audiorecord")),
                ("requested_by", models.ForeignKey(blank=True, help_text="분석을 요청한 사용자", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="voice_analyses", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Voice analysis",
                "verbose_name_plural": "Voice analyses",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="voiceanalysis",
            index=models.Index(fields=["analysis_type", "status"], name="voice_analy_analysi_11cf83_idx"),
        ),
        migrations.AddIndex(
            model_name="voiceanalysis",
            index=models.Index(fields=["created_at"], name="voice_analy_created_52df70_idx"),
        ),
    ]