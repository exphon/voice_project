from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
from .models import AudioRecord

class AudioUploadView(APIView):
    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')  # ⭐ 'file'로 받아야 합니다
        gender = request.POST.get('gender')  # ⭐ 추가
        age = request.POST.get('age')        # ⭐ 추가

        if not file:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        record = AudioRecord.objects.create(
            audio_file=file,
            gender=gender,
            age=age,
        )
        return Response({'message': 'Upload success', 'file_path': record.audio_file.url})

def audio_list(request):
    audios = AudioRecord.objects.all().order_by('-created_at')  # 최신순 정렬
    return render(request, 'voice_app/audio_list.html', {'audios': audios})
