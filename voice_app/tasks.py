# voice_app/tasks.py

from .models import AudioRecord
from .whisper_utils import transcribe_audio

def transcribe_audio_task(audio_id):
    audio = None  # 예외 발생 시 참조할 수 있도록 미리 정의

    try:
        audio = AudioRecord.objects.get(id=audio_id)
        audio.status = 'processing'
        audio.save()

        result = transcribe_audio(audio.audio_file.path)
        if result:
            audio.transcription = result
            audio.status = 'completed'
        else:
            audio.status = 'failed'
        audio.save()

    except AudioRecord.DoesNotExist:
        print(f"[Error] AudioRecord with ID {audio_id} not found.")
    except Exception as e:
        if audio:
            audio.status = 'failed'
            audio.save()
        print(f"[Error] Transcription failed for ID {audio_id}: {e}")
