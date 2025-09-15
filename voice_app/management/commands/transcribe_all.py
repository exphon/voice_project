# voice_app/management/commands/transcribe_all.py
# -*- coding: utf-8 -*-
"""
python manage.py transcribe_all
"""

import os
import whisper
from django.core.management.base import BaseCommand
from django.conf import settings
from voice_app.models import AudioRecord

class Command(BaseCommand):
    help = "Whisper로 모든 음성 파일을 일괄 전사"

    def handle(self, *args, **options):
        model = whisper.load_model("base")  # 필요시 'small', 'medium' 등으로 조정

        for record in AudioRecord.objects.filter(transcription__isnull=True):
            wav_path = os.path.join(settings.MEDIA_ROOT, str(record.audio_file))
            if not os.path.exists(wav_path):
                self.stdout.write(self.style.WARNING(f"파일 없음: {wav_path}"))
                continue

            try:
                result = model.transcribe(wav_path, language='ko')
                record.transcription = result['text']
                record.save()
                self.stdout.write(self.style.SUCCESS(f"✅ 전사 완료: {record.id}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ 전사 실패 ({record.id}): {e}"))