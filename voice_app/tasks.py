# voice_app/tasks.py

from .models import AudioRecord
from .whisper_utils import transcribe_audio
import os

def transcribe_audio_task(audio_id):
    audio = None  # 예외 발생 시 참조할 수 있도록 미리 정의
    
    print(f"[Task] transcribe_audio_task started for audio ID: {audio_id}")

    try:
        audio = AudioRecord.objects.get(id=audio_id)
        print(f"[Task] AudioRecord found: ID={audio.id}")
        
        audio.status = 'processing'
        audio.save()
        print(f"[Task] Status set to 'processing'")

        # 파일 경로 확인
        audio_path = audio.audio_file.path
        print(f"[Task] Audio file path: {audio_path}")
        
        if not os.path.exists(audio_path):
            print(f"[Task Error] Audio file does not exist: {audio_path}")
            audio.status = 'failed'
            audio.save()
            return
        
        print(f"[Task] Audio file exists, size: {os.path.getsize(audio_path)} bytes")
        print(f"[Task] Calling transcribe_audio()...")
        
        result = transcribe_audio(audio_path)
        
        print(f"[Task] transcribe_audio() returned: {result[:100] if result else 'None'}...")
        
        if result:
            audio.transcript = result  # Whisper 자동 전사 결과
            # manual_transcript가 비어있으면 자동 전사 결과로 초기화
            if not audio.manual_transcript:
                audio.manual_transcript = result
            audio.status = 'completed'
            print(f"[Task Success] Transcription completed for ID {audio_id}")
        else:
            audio.status = 'failed'
            print(f"[Task Failed] No transcription result for ID {audio_id}")
        audio.save()

    except AudioRecord.DoesNotExist:
        print(f"[Task Error] AudioRecord with ID {audio_id} not found.")
    except Exception as e:
        print(f"[Task Error] Exception in transcription for ID {audio_id}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        if audio:
            audio.status = 'failed'
            audio.save()

