import os, uuid, whisper
import subprocess
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from django.conf import settings
from django.shortcuts import render, redirect
from .models import AudioRecord
from pydub import AudioSegment

whisper_model = whisper.load_model("medium")  # 'base', 'small', 'medium', 'large' 중 선택

# ffmpeg 경로 명시
AudioSegment.converter = "/opt/homebrew/bin/ffmpeg"  # 사용 환경에 맞게 조정

def convert_m4a_to_wav(m4a_path, wav_path):
    try:
        result = subprocess.run(
            ['ffmpeg', '-i', m4a_path, wav_path, '-y'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        print("✅ ffmpeg 변환 성공:", result.stdout.decode())
    except subprocess.CalledProcessError as e:
        print("❌ ffmpeg 변환 실패:", e.stderr.decode())

def is_audio_silent(wav_path, threshold_dbfs=-40.0):
    audio = AudioSegment.from_wav(wav_path)
    return audio.dBFS < threshold_dbfs

def transcribe_audio_whisper(wav_path):
    result = whisper_model.transcribe(wav_path, language='ko')  # 한글 강제 설정
    return result['text']

class AudioUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        file = request.data.get('file')
        gender = request.data.get('gender')  # ⭐ 추가
        age = request.data.get('age')        # ⭐ 추가

        if not file:
            return Response({'error': '파일이 없습니다.'}, status=400)
        
        # 🎯 여기서 서버단 UUID로 파일명 다시 설정
        ext = file.name.split('.')[-1]  # 확장자 얻기
        unique_filename = f"{uuid.uuid4().hex}.{ext}"
        file.name = unique_filename

        audio_record = AudioRecord.objects.create(audio_file=file,
                                                  gender=gender,
                                                  age=age)
        m4a_path = audio_record.audio_file.path
        wav_path = m4a_path.replace('.m4a', '.wav')

        # ⭐ 1. 변환
        convert_m4a_to_wav(m4a_path, wav_path)

        # ⭐ 2. 무음 체크
        if is_audio_silent(wav_path):
            # 무음이면 모두 삭제
            audio_record.delete()
            if os.path.exists(m4a_path):
                os.remove(m4a_path)
            if os.path.exists(wav_path):
                os.remove(wav_path)
            return Response({'message': '무음 파일은 삭제되었습니다.'}, status=400)
        else:
            # 정상 발화: m4a 삭제, wav만 남기기
            if os.path.exists(m4a_path):
                os.remove(m4a_path)
            
            # 🧠 Whisper로 transcription 수행
            transcription_text = transcribe_audio_whisper(wav_path)
            audio_record.transcript = transcription_text
            # manual_transcript가 비어있으면 자동 전사 결과로 초기화
            if not audio_record.manual_transcript:
                audio_record.manual_transcript = transcription_text
            audio_record.save()

            return Response({'message': '업로드 성공', 
                            'file_path': audio_record.audio_file.url,
                            'transcript': transcription_text
                             })
        
def audio_list(request):
    audios = AudioRecord.objects.all().order_by('-created_at')  # 최신순 정렬
    return render(request, 'voice_app/audio_list.html', {'audios': audios})

def delete_all_audios(request):
    if request.method == 'POST':
        audios = AudioRecord.objects.all()
        for record in audios:
            file_path = os.path.join(settings.MEDIA_ROOT, record.audio_file.name)
            if os.path.exists(file_path):
                os.remove(file_path)
            record.delete()
        return redirect('audio-list')  # ⭐ 이거 반드시 리턴해야 해요
    else:
        return redirect('audio-list')  # ⭐ GET 요청이 오더라도 안전하게 리턴