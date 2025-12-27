# voice_app/management/commands/transcribe_all.py
# -*- coding: utf-8 -*-
"""
python manage.py transcribe_all
"""

import os
import whisper
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Q
from voice_app.models import AudioRecord

class Command(BaseCommand):
    help = "Whisper로 모든 음성 파일을 일괄 전사"

    def handle(self, *args, **options):
        model = whisper.load_model("large-v3")

        # 정책: "전사 내용(manual_transcript)"과 "Whisper 자동 전사(transcript)"가 모두 비어있는 경우에만 전사
        empty_manual = Q(manual_transcript__isnull=True) | Q(manual_transcript='')
        empty_auto = Q(transcript__isnull=True) | Q(transcript='')
        for record in AudioRecord.objects.filter(empty_manual).filter(empty_auto):
            wav_path = os.path.join(settings.MEDIA_ROOT, str(record.audio_file))
            if not os.path.exists(wav_path):
                self.stdout.write(self.style.WARNING(f"파일 없음: {wav_path}"))
                continue

            try:
                result = model.transcribe(
                    wav_path,
                    language='ko',
                    task='transcribe',
                    temperature=0.0,
                    initial_prompt='다음은 한국어 음성의 전사입니다. 가능한 한 정확히, 반드시 한국어로만 전사하세요.',
                )
                text = result.get('text')
                record.transcript = text
                if not record.manual_transcript:
                    record.manual_transcript = text
                record.save()
                self.stdout.write(self.style.SUCCESS(f"✅ 전사 완료: {record.id}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ 전사 실패 ({record.id}): {e}"))