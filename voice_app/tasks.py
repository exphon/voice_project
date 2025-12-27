# voice_app/tasks.py

from .models import AudioRecord
from .whisper_utils import transcribe_audio, transcribe_audio_mixed_child_adult
import os

def transcribe_audio_task(audio_id, overwrite_manual_transcript: bool = False):
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

        # 5살 이하 아동(또는 아동 카테고리/나이 정보 누락)에서 혼합 발화 대응 파이프라인 사용
        is_young_child = False
        try:
            if audio.age_in_months is not None and int(audio.age_in_months) <= 60:
                is_young_child = True
        except Exception:
            pass
        try:
            if audio.age and str(audio.age).isdigit() and int(audio.age) <= 5:
                is_young_child = True
        except Exception:
            pass
        if audio.category == 'child' and (audio.age_in_months is None and not (audio.age and str(audio.age).isdigit())):
            is_young_child = True

        diarization_payload = None
        if is_young_child:
            print(f"[Task] Using mixed child+adult pipeline (diarization/VAD)...")
            out = transcribe_audio_mixed_child_adult(audio_path, prefer_diarization=True)
            result = out.get('text')
            diarization_payload = out.get('diarization')
            # diarization이 성공적으로 수행된 경우 DB에 저장
            if diarization_payload and isinstance(diarization_payload, dict):
                audio.diarization_data = diarization_payload
                audio.diarization_status = diarization_payload.get('status', 'completed') if out.get('mode') == 'diarization' else 'unprocessed'
                audio.num_speakers = diarization_payload.get('num_speakers')
        else:
            result = transcribe_audio(audio_path)
        
        print(f"[Task] transcribe_audio() returned: {result[:100] if result else 'None'}...")
        
        if result:
            audio.transcript = result  # Whisper 자동 전사 결과
            # manual_transcript가 비어있으면 자동 전사 결과로 초기화
            # 또는 (전사 버튼 등) overwrite_manual_transcript=True 인 경우 강제로 덮어씀
            if overwrite_manual_transcript or not audio.manual_transcript:
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

