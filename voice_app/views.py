# 백그라운드 노이즈 업로드 API
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class UploadBackgroundNoise(APIView):
    def post(self, request):
        session_id = request.data.get('session_id')
        file = request.FILES.get('file')
        if not session_id or not file:
            return Response({'error': 'Missing session_id or file'}, status=status.HTTP_400_BAD_REQUEST)
        
        # AudioRecord로 임시 저장 (SessionNoise 모델이 없으므로)
        from .models import AudioRecord
        noise_record = AudioRecord.objects.create(
            audio_file=file,
            category='normal',
            diagnosis=f'background_noise_session_{session_id}'
        )
        return Response({'message': 'Uploaded', 'id': noise_record.id}, status=status.HTTP_201_CREATED)
# views.py (업로드만 수행, Whisper 전사 제거)

import os, uuid
import subprocess
import whisper
import json
import base64
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.decorators import api_view

from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .tasks import transcribe_audio_task
from django.views.generic import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from .models import AudioRecord
from pydub import AudioSegment  # 의존성 때문에 임시 주석
from .whisper_utils import transcribe_audio, transcribe_and_align_whisperx, format_alignment_for_frontend  # whisperx 의존성 때문에 임시 주석




# ffmpeg 경로 명시 (Linux 서버) - pydub 의존성 때문에 임시 주석
# AudioSegment.converter = "/usr/bin/ffmpeg"  # Linux 환경에 맞게 조정

def convert_m4a_to_wav(input_path, output_path):
    """Convert audio file to wav using ffmpeg with enhanced error handling and corruption recovery"""
    print(f"[DEBUG] Starting conversion from {input_path} to {output_path}")
    
    # Check if input file exists
    if not os.path.exists(input_path):
        error_msg = f"Input file does not exist: {input_path}"
        print(f"[ERROR] {error_msg}")
        raise FileNotFoundError(error_msg)
    
    print(f"[DEBUG] Input file exists, size: {os.path.getsize(input_path)} bytes")
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)
    print(f"[DEBUG] Output directory created/verified: {output_dir}")
    
    # Check if input and output paths are the same
    if os.path.abspath(input_path) == os.path.abspath(output_path):
        print(f"[DEBUG] Input and output paths are the same, using temporary file approach")
        temp_output = output_path + '.tmp.wav'
        
        command = [
            'ffmpeg', '-y', '-i', input_path,
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            temp_output
        ]
        
        print(f"[DEBUG] Same-file conversion using temp: {temp_output}")
        use_temp_file = True
    else:
        # Different paths - direct conversion
        command = [
            'ffmpeg', '-y', '-i', input_path,
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            output_path
        ]
        use_temp_file = False
    
    try:
        print(f"[DEBUG] Running ffmpeg command: {' '.join(command)}")
        
        # Execute ffmpeg
        result = subprocess.run(command, 
                              capture_output=True, 
                              text=True, 
                              timeout=60)
        
        print(f"[DEBUG] ffmpeg return code: {result.returncode}")
        if result.stdout:
            print(f"[DEBUG] ffmpeg stdout: {result.stdout}")
        if result.stderr:
            print(f"[DEBUG] ffmpeg stderr: {result.stderr}")
        
        if result.returncode != 0:
            # Check for specific corruption issues
            if "moov atom not found" in result.stderr:
                print("[INFO] moov atom 누락 감지, 복구 시도 중...")
                
                # Try recovery with ffmpeg error detection disabled
                print("[INFO] FFmpeg recover 옵션으로 시도")
                recovery_command = [
                    'ffmpeg', '-y', '-err_detect', 'ignore_err', '-i', input_path,
                    '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
                    temp_output if use_temp_file else output_path
                ]
                
                recovery_result = subprocess.run(recovery_command,
                                               capture_output=True,
                                               text=True,
                                               timeout=60)
                
                print(f"[DEBUG] Recovery ffmpeg return code: {recovery_result.returncode}")
                if recovery_result.stderr:
                    print(f"[DEBUG] Recovery ffmpeg stderr: {recovery_result.stderr}")
                
                if recovery_result.returncode == 0:
                    print("[SUCCESS] 손상된 파일 복구 성공")
                    result = recovery_result  # Use recovery result for further processing
                else:
                    error_msg = f"M4A 파일이 심각하게 손상되었습니다 (moov atom 누락). React Native 앱의 MediaRecorder 설정을 확인해주세요. 원본 오류: {result.stderr}"
                    print(f"[ERROR] {error_msg}")
                    raise Exception(error_msg)
            else:
                error_msg = f"ffmpeg conversion failed: {result.stderr}"
                print(f"[ERROR] {error_msg}")
                raise Exception(error_msg)
        
        # Handle temporary file if used
        if use_temp_file:
            temp_output = output_path + '.tmp.wav'
            if os.path.exists(temp_output):
                # Remove original and rename temp file
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(temp_output, output_path)
                print(f"[DEBUG] Moved temp file to final location: {output_path}")
            else:
                error_msg = f"Temp output file was not created: {temp_output}"
                print(f"[ERROR] {error_msg}")
                raise FileNotFoundError(error_msg)
        
        # Check if output file was created
        if not os.path.exists(output_path):
            error_msg = f"Output file was not created: {output_path}"
            print(f"[ERROR] {error_msg}")
            raise FileNotFoundError(error_msg)
        
        print(f"[SUCCESS] Successfully converted {input_path} to {output_path}")
        print(f"[DEBUG] Output file size: {os.path.getsize(output_path)} bytes")
        
        return True
        
    except subprocess.TimeoutExpired:
        error_msg = "ffmpeg conversion timed out"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Conversion error: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise
        if not os.path.exists(output_path):
            error_msg = f"Output file was not created: {output_path}"
            print(f"[ERROR] {error_msg}")
            raise FileNotFoundError(error_msg)
        
        print(f"[SUCCESS] Successfully converted {input_path} to {output_path}")
        print(f"[DEBUG] Output file size: {os.path.getsize(output_path)} bytes")
        
        return True
        
    except subprocess.TimeoutExpired:
        error_msg = "ffmpeg conversion timed out"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Conversion error: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise

def is_audio_silent(wav_path, threshold_dbfs=-40.0):
    # AudioSegment 의존성 때문에 임시로 False 반환
    # audio = AudioSegment.from_wav(wav_path)
    # return audio.dBFS < threshold_dbfs
    return False  # 임시로 무음이 아닌 것으로 처리

# 누락된 API 엔드포인트들 추가
@api_view(['GET'])
def api_child_info(request):
    """아동 정보 API"""
    return Response({
        'message': 'Child info API',
        'version': '1.0',
        'categories': ['child', 'senior', 'atypical', 'auditory', 'normal']
    })

@api_view(['GET'])
def api_status(request):
    """시스템 상태 API"""
    return Response({
        'status': 'running',
        'server': 'Django Voice Management',
        'version': '1.0'
    })

@api_view(['GET'])
def api_config(request):
    """설정 정보 API"""
    return Response({
        'upload_formats': ['wav', 'm4a', 'mp3', 'opus'],
        'max_file_size': '50MB',
        'sample_rate': 16000,
        'channels': 1
    })

@method_decorator(csrf_exempt, name='dispatch')
class AudioUploadView(APIView):
    """
    음성 파일 및 메타데이터 업로드 API
    
    지원 파일 형식:
    - 오디오: .wav, .mp3, .m4a, .flac, .mp4, .webm, .ogg
    - 메타데이터: .json (오디오 파일과 동일한 이름으로 업로드 가능)
    
    업로드 방법:
    1. 오디오 파일만 업로드 + metadata_json 필드에 JSON 문자열 전달
    2. 오디오 파일 + JSON 파일 동시 업로드 (선호)
    
    FormData 예시:
        formData.append('file', audioFile);  // 오디오 파일
        formData.append('metadata_file', jsonFile);  // JSON 메타데이터 파일 (선택)
        formData.append('metadata_json', JSON.stringify(metadata));  // 또는 JSON 문자열
    """
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        try:
            print(f"[DEBUG] Upload request from {request.META.get('REMOTE_ADDR')}")
            print(f"[DEBUG] Content-Type: {request.content_type}")
            print(f"[DEBUG] Files: {list(request.FILES.keys())}")
            print(f"[DEBUG] Data keys: {list(request.data.keys())}")
            # 추가 헤더/환경 정보
            ua = request.META.get('HTTP_USER_AGENT', 'N/A')
            print(f"[DEBUG] User-Agent: {ua}")
            print(f"[DEBUG] RAW Content-Length header: {request.META.get('HTTP_CONTENT_LENGTH')}")
            # multipart/form-data 에서 boundary 누락/손상 시도 진단
            if request.content_type and 'multipart/form-data' in request.content_type and 'boundary=' not in request.content_type:
                print("[WARN] multipart/form-data 이지만 boundary 파라미터가 없습니다 - 클라이언트 Content-Type 강제 지정 오류 가능성")
            
            # Request 내용 자세히 살펴보기
            print(f"[DEBUG] Request method: {request.method}")
            print(f"[DEBUG] Request encoding: {request.encoding}")
            print(f"[DEBUG] Request META Content-Length: {request.META.get('CONTENT_LENGTH', 'Not set')}")
            
            # 파일 필드 디버깅
            for key, value in request.data.items():
                if key == 'file':
                    print(f"[DEBUG] File field value: {value}")
                    print(f"[DEBUG] File field type: {type(value)}")
                    print(f"[DEBUG] File field repr: {repr(value)}")
                    if hasattr(value, '__dict__'):
                        print(f"[DEBUG] File field attributes: {vars(value)}")
            
            # Raw POST data 확인
            if hasattr(request, '_body') and request._body:
                body_preview = request._body[:500] if len(request._body) > 500 else request._body
                print(f"[DEBUG] Raw body preview (first 500 bytes): {body_preview}")
            
            # 업로드된 파일들 분석 (오디오/메타데이터 분리)
            file = None
            metadata_file = None
            file_candidates = list(request.FILES.items())

            if file_candidates:
                preferred_audio_keys = {'file', 'audio', 'audio_file', 'audiofile', 'recording', 'voice'}
                preferred_metadata_keys = {'metadata_json', 'metadata', 'metadata_file', 'json', 'meta'}

                # 1차: 키 기반 선호 탐색
                for key, value in file_candidates:
                    key_lower = key.lower()
                    if not file and key_lower in preferred_audio_keys:
                        file = value
                    if not metadata_file and key_lower in preferred_metadata_keys:
                        metadata_file = value
                    if file and metadata_file:
                        break

                # 2차: 콘텐츠 타입 기반 탐색
                if not file:
                    for _, value in file_candidates:
                        content_type = getattr(value, 'content_type', '') or ''
                        if content_type.startswith('audio/'):
                            file = value
                            break

                if not metadata_file:
                    for _, value in file_candidates:
                        content_type = getattr(value, 'content_type', '') or ''
                        name = getattr(value, 'name', '') or ''
                        if content_type in ('application/json', 'text/json') or name.lower().endswith('.json'):
                            metadata_file = value
                            if value is not file:
                                break

                # 3차: 최후 수단 - 첫 번째 파일
                if not file and file_candidates:
                    file = file_candidates[0][1]

            else:
                metadata_file = None
            if not file:
                print(f"[ERROR] No file in request. Available FILES keys: {list(request.FILES.keys())}")
                print(f"[ERROR] All POST data keys: {list(request.data.keys())}")
                # 원인 1: React Native fetch에 Content-Type을 직접 지정 → boundary 손실
                print("[HINT] React Native에서 FormData 전송 시 'Content-Type' 헤더를 수동 지정하지 말고 fetch가 자동 생성하도록 해야 합니다.")
                
                # 'file' 필드가 data에 있는지 확인
                if 'file' in request.data:
                    file_data = request.data.get('file')
                    print(f"[ERROR] File found in data but not FILES: {file_data}")
                    print(f"[ERROR] File data type: {type(file_data)}")
                
                # React Native에서 보내는 Content-Type 확인
                boundary = None
                if 'boundary=' in request.content_type:
                    boundary = request.content_type.split('boundary=')[1]
                    print(f"[DEBUG] Detected boundary: {boundary}")
                else:
                    print("[WARN] Boundary 문자열을 Content-Type에서 찾지 못했습니다.")

                # raw body를 임시 파일로 저장 (사이즈 5MB 이하 제한) - 이미 consume 된 경우 대체 시도
                body_bytes = b''
                try:
                    # Django에서 body가 이미 읽혀 사라진 경우 대비
                    if hasattr(request, '_body') and request._body:
                        body_bytes = request._body
                    else:
                        try:
                            body_bytes = request.body  # 아직 접근 가능하면 사용
                        except Exception as e_in:
                            print(f"[DEBUG] Direct request.body access failed: {e_in}")
                    if body_bytes:
                        max_dump = 5 * 1024 * 1024
                        dump_len = min(len(body_bytes), max_dump)
                        dump_path = os.path.join(settings.MEDIA_ROOT, 'debug_upload_body.dump')
                        with open(dump_path, 'wb') as f:
                            f.write(body_bytes[:dump_len])
                        print(f"[DEBUG] Saved raw body dump ({dump_len} bytes) to {dump_path}")
                    else:
                        print("[DEBUG] No raw body bytes captured (empty or already consumed)")
                except Exception as e:
                    print(f"[DEBUG] Failed to dump raw body: {e}")

                # 수동 multipart 파싱 시도 (boundary와 body가 있는 경우)
                recovered_file_info = None
                try:
                    if boundary and body_bytes:
                        boundary_token = ('--' + boundary).encode()
                        parts = body_bytes.split(boundary_token)
                        for part in parts:
                            if b'Content-Disposition' in part and b'filename=' in part:
                                header, _, content = part.partition(b'\r\n\r\n')
                                if not content:
                                    continue
                                # part 종료 시그니처 제거
                                content = content.rstrip(b'\r\n')
                                if content.endswith(b'--'):
                                    content = content[:-2]
                                try:
                                    header_str = header.decode(errors='ignore')
                                    import re
                                    fn_match = re.search(r'filename="([^"]+)"', header_str)
                                    original_name = fn_match.group(1) if fn_match else 'recovered.bin'
                                except Exception:
                                    original_name = 'recovered.bin'
                                from django.core.files.uploadedfile import InMemoryUploadedFile
                                from io import BytesIO
                                file_buf = BytesIO(content)
                                recovered = InMemoryUploadedFile(
                                    file=file_buf,
                                    field_name='file',
                                    name=original_name,
                                    content_type='application/octet-stream',
                                    size=len(content),
                                    charset=None
                                )
                                recovered_file_info = {'name': original_name, 'size': len(content)}
                                print(f"[DEBUG] Recovered file from raw multipart: {recovered_file_info}")
                                file = recovered
                                break
                    else:
                        print("[DEBUG] Manual multipart parsing skipped (missing boundary or body)")
                except Exception as e:
                    print(f"[DEBUG] Manual multipart parsing failed: {e}")

                if not file:
                    return Response({
                        'error': '파일이 없습니다. React Native 앱에서 FormData 구성을 재확인하세요.',
                        'debug': {
                            'files_keys': list(request.FILES.keys()),
                            'data_keys': list(request.data.keys()),
                            'content_type': request.content_type,
                            'boundary': boundary,
                            'user_agent': ua,
                            'recovered_file': recovered_file_info,
                            'hint': 'fetch 호출 시 headers에 Content-Type을 직접 넣지 말고 FormData append 후 그대로 전송'
                        }
                    }, status=400)

                # 여기까지 왔다면 수동 복구 성공 → 이후 정상 처리 계속
                print("[INFO] Proceeding with recovered file flow")
                
            
            print(f"[DEBUG] File received: {file.name}, size: {file.size}")
            
            # 모든 POST 데이터 추출
            name = request.data.get('name')
            gender = request.data.get('gender')
            age = request.data.get('age')
            birth_date = request.data.get('birthDate')  # YYYY-MM-DD 형식
            recording_date = request.data.get('recordingDate')
            region = request.data.get('region')
            place = request.data.get('place')
            noise = request.data.get('noise')
            pronun_problem = request.data.get('pronunProblem')
            diagnosis = request.data.get('diagnosis')
            device = request.data.get('device')
            mic = request.data.get('mic')
            subjective_rating = request.data.get('subjective_rating')
            sentence_index = request.data.get('sentence_index')
            sentence_text = request.data.get('sentence_text')
            task_type = request.data.get('task_type')
            upload_timestamp = request.data.get('upload_timestamp')
            local_saved = request.data.get('local_saved')
            metadata_json = request.data.get('metadata_json')
            identifier = request.data.get('identifier')

            if identifier is not None:
                identifier = str(identifier).strip().upper()
                if not identifier:
                    identifier = None
            print(f"[DEBUG] Identifier from request: {identifier}")
            
            # 카테고리별 고유 필드 추출
            # Child 고유
            age_in_months = request.data.get('ageInMonths')
            
            # Senior 고유
            education = request.data.get('education')
            education_years = request.data.get('educationYears')
            final_education = request.data.get('finalEducation') or request.data.get('educationLevel')
            education_detail = request.data.get('educationDetail')
            cognitive_decline = request.data.get('cognitiveDecline')
            subjective_score = request.data.get('subjectiveScore')
            subjective_note = request.data.get('subjectiveNote')
            job = request.data.get('job')
            
            # Auditory 고유 - 청각 관련
            hearing_level = request.data.get('hearingLevel') or request.data.get('hearingDegree')
            hearing_loss_duration = request.data.get('hearingLossDuration')
            has_hearing_aid = request.data.get('hasHearingAid')
            hearing_aid_duration = request.data.get('hearingAidDuration')
            hearing_onset_type = request.data.get('hearingOnsetType')
            hearing_impairment = request.data.get('hearingImpairment')
            
            # Auditory 고유 - 인지 관련
            cognitive_level = request.data.get('cognitiveLevel') or request.data.get('cognitiveImpairment')
            
            # Auditory 고유 - 언어 관련
            native_language = request.data.get('nativeLanguage')
            language_experience = request.data.get('languageExperience')
            
            # Auditory 고유 - 배경소음 측정
            session_id = request.data.get('session_id')
            background_noise_average = request.data.get('background_noise_average')
            background_noise_max = request.data.get('background_noise_max')
            background_noise_min = request.data.get('background_noise_min')
            noise_measurement_time = request.data.get('noise_measurement_time')
            platform = request.data.get('platform')
            
            # 작업 특화 정보
            retry_count = request.data.get('retry_count')
            attempt = request.data.get('attempt')
            question_file = request.data.get('question_file')
            current_page = request.data.get('current_page')
            page_name = request.data.get('page_name')
            
            metadata_from_file = None
            metadata_filename = None

            # JSON 파일 업로드 처리
            if metadata_file:
                try:
                    metadata_bytes = metadata_file.read()
                    metadata_text = metadata_bytes.decode('utf-8', errors='ignore').strip()
                    if metadata_text:
                        metadata_from_file = metadata_text
                        metadata_filename = metadata_file.name
                        if not metadata_json:
                            metadata_json = metadata_from_file
                        print(f"[DEBUG] Metadata JSON file received: {metadata_filename}, size: {len(metadata_bytes)} bytes")
                    else:
                        print(f"[DEBUG] Metadata file {metadata_file.name} is empty after decoding")
                except Exception as e:
                    print(f"[DEBUG] Failed to read metadata JSON file: {e}")
            
            # metadata_json에서 메타 정보 추출 (React Native에서는 주로 이 방식 사용)
            if metadata_json:
                try:
                    # 먼저 문자열인지 확인
                    if isinstance(metadata_json, str):
                        metadata = json.loads(metadata_json)
                    else:
                        # 이미 딕셔너리인 경우
                        metadata = metadata_json
                        
                    print(f"[DEBUG] Parsing metadata_json: {metadata}")
                    
                    # metainfo_child에서 정보 추출
                    if 'metainfo_child' in metadata:
                        metainfo = metadata['metainfo_child']
                        name = name or metainfo.get('name')
                        gender = gender or metainfo.get('gender')
                        birth_date = birth_date or metainfo.get('birthDate')
                        age = age or metainfo.get('age')
                        recording_date = recording_date or metainfo.get('recordingDate')
                        region = region or metainfo.get('region')
                        place = place or metainfo.get('place')
                        noise = noise or metainfo.get('noise')
                        pronun_problem = pronun_problem or metainfo.get('pronunProblem')
                        diagnosis = diagnosis or metainfo.get('diagnosis')
                        device = device or metainfo.get('device')
                        mic = mic or metainfo.get('mic')
                    
                    # metainfo_senior에서 정보 추출 (노인 카테고리)
                    if 'metainfo_senior' in metadata:
                        metainfo = metadata['metainfo_senior']
                        name = name or metainfo.get('name')
                        gender = gender or metainfo.get('gender')
                        birth_date = birth_date or metainfo.get('birthDate')
                        age = age or metainfo.get('age')
                        recording_date = recording_date or metainfo.get('recordingDate')
                        region = region or metainfo.get('region')
                        place = place or metainfo.get('place') or metainfo.get('recordingLocation')
                        noise = noise or metainfo.get('noise') or metainfo.get('noiseLevel')
                        diagnosis = diagnosis or metainfo.get('diagnosis')
                        device = device or metainfo.get('device') or metainfo.get('deviceType')
                        mic = mic or metainfo.get('mic') or metainfo.get('hasMicrophone')
                    
                    # task_info에서 정보 추출
                    if 'task_info' in metadata:
                        task_info_data = metadata['task_info']
                        task_type = task_type or task_info_data.get('task_type')
                        if task_info_data.get('current_sentence_index') is not None:
                            sentence_index = sentence_index or str(task_info_data['current_sentence_index'])
                        elif task_info_data.get('sentence_index') is not None:
                            sentence_index = sentence_index or str(task_info_data['sentence_index'])
                        sentence_text = sentence_text or task_info_data.get('sentence_text')
                    
                    # upload_info에서 정보 추출
                    if 'upload_info' in metadata:
                        upload_info_data = metadata['upload_info']
                        subjective_rating = subjective_rating or upload_info_data.get('subjective_rating')
                        upload_timestamp = upload_timestamp or upload_info_data.get('upload_timestamp')
                    
                    print(f"[DEBUG] After metadata extraction - name: {name}, gender: {gender}, task_type: {task_type}")
                    print(f"[DEBUG] Region: {region}, Device: {device}, Age: {age}")
                    
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] Failed to parse metadata_json as JSON: {e}")
                    # Base64 디코딩이 필요한지 확인
                    try:
                        if isinstance(metadata_json, str):
                            decoded_bytes = base64.b64decode(metadata_json)
                            decoded_str = decoded_bytes.decode('utf-8')
                            metadata = json.loads(decoded_str)
                            print(f"[DEBUG] Successfully decoded Base64 metadata: {metadata}")
                    except Exception as e2:
                        print(f"[DEBUG] Base64 decode also failed: {e2}")
                except Exception as e:
                    print(f"[DEBUG] Error extracting from metadata_json: {e}")
            
            # SNR 값들 추출
            snr_mean = request.data.get('snr_mean')
            snr_max = request.data.get('snr_max')
            snr_min = request.data.get('snr_min')
            
            # birthDate 파싱 (YYYY-MM-DD 형식에서 년/월/일 분리)
            birth_year = birth_month = birth_day = None
            if birth_date:
                try:
                    parts = birth_date.split('-')
                    if len(parts) == 3:
                        birth_year = parts[0]
                        birth_month = parts[1]
                        birth_day = parts[2]
                    print(f"[DEBUG] Parsed birth date: {birth_year}-{birth_month}-{birth_day}")
                except Exception as e:
                    print(f"[DEBUG] Birth date parsing error: {e}")
            
            print(f"[DEBUG] Extracted data - name: {name}, gender: {gender}, region: {region}, place: {place}")
            print(f"[DEBUG] Device info - device: {device}, mic: {mic}, noise: {noise}")
            print(f"[DEBUG] Task info - task_type: {task_type}, sentence_index: {sentence_index}")
            
            # URL에서 카테고리 추출하거나 POST 데이터에서 가져오기
            category = kwargs.get('category') or request.data.get('category', 'normal')

            # 카테고리 유효성 검사 (auditory 추가)
            valid_categories = ['child', 'senior', 'atypical', 'auditory', 'normal']
            if category not in valid_categories:
                category = 'normal'

            # 고유 파일명 생성
            # 확장자 결정 로직 (파일명이 확장자를 포함하지 않을 수도 있음)
            if '.' in (file.name or ''):
                ext = file.name.split('.')[-1]
            else:
                # content_type 기반 추정
                ct = getattr(file, 'content_type', '') or ''
                if 'wav' in ct:
                    ext = 'wav'
                elif 'm4a' in ct or 'mp4' in ct:
                    ext = 'm4a'
                elif 'mpeg' in ct or 'mp3' in ct:
                    ext = 'mp3'
                elif 'ogg' in ct or 'opus' in ct:
                    ext = 'opus'
                else:
                    # 기본값: wav로 저장 시도
                    ext = 'wav'
            unique_id = uuid.uuid4().hex
            m4a_filename = f"{unique_id}.{ext}"
            
            # 카테고리별 저장 경로 생성
            category_folder = os.path.join('audio', category)
            m4a_storage_path = os.path.join(category_folder, m4a_filename)

            # 카테고리 폴더가 없으면 생성
            category_media_folder = os.path.join(settings.MEDIA_ROOT, category_folder)
            os.makedirs(category_media_folder, exist_ok=True)

            # m4a 파일 저장
            file_data = ContentFile(file.read())
            m4a_full_path = default_storage.save(m4a_storage_path, file_data)
            m4a_path = os.path.join(settings.MEDIA_ROOT, m4a_full_path)
            
            print(f"[DEBUG] Saved file path: {m4a_full_path}")
            print(f"[DEBUG] Full file path: {m4a_path}")

            # 실제 저장된 파일명에서 고유 ID 추출 (확장자 제거)
            saved_filename = os.path.basename(m4a_full_path)
            saved_unique_id = os.path.splitext(saved_filename)[0]
            print(f"[DEBUG] Extracted unique ID from saved file: {saved_unique_id}")

            # wav 변환 경로 지정 (실제 저장된 고유 ID 사용)
            wav_filename = f"{saved_unique_id}.wav"
            wav_path = os.path.join(settings.MEDIA_ROOT, category_folder, wav_filename)
            
            print(f"[DEBUG] Target WAV file: {wav_path}")

            # 변환 실행
            print(f"[DEBUG] Input file extension: {ext}")
            
            # WAV 파일이고 이미 올바른 형식인지 확인
            if ext.lower() == 'wav':
                # WAV 파일 정보 확인
                try:
                    result = subprocess.run([
                        'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                        '-show_format', '-show_streams', m4a_path
                    ], capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0:
                        info = json.loads(result.stdout)
                        
                        # 오디오 스트림 정보 추출
                        audio_stream = None
                        for stream in info.get('streams', []):
                            if stream.get('codec_type') == 'audio':
                                audio_stream = stream
                                break
                        
                        if audio_stream:
                            sample_rate = int(audio_stream.get('sample_rate', 0))
                            channels = int(audio_stream.get('channels', 0))
                            codec = audio_stream.get('codec_name', '')
                            
                            print(f"[DEBUG] WAV file info - Sample rate: {sample_rate}, Channels: {channels}, Codec: {codec}")
                            
                            # 이미 16kHz 모노 PCM인 경우 변환 건너뛰기
                            if sample_rate == 16000 and channels == 1 and codec == 'pcm_s16le':
                                print(f"[DEBUG] WAV file already in correct format, copying instead of converting")
                                # 단순히 파일을 복사
                                import shutil
                                shutil.copy2(m4a_path, wav_path)
                                convert_success = True
                            else:
                                print(f"[DEBUG] WAV file needs conversion")
                                convert_success = convert_m4a_to_wav(m4a_path, wav_path)
                        else:
                            print(f"[DEBUG] Could not extract audio stream info, proceeding with conversion")
                            convert_success = convert_m4a_to_wav(m4a_path, wav_path)
                    else:
                        print(f"[DEBUG] ffprobe failed, proceeding with conversion")
                        convert_success = convert_m4a_to_wav(m4a_path, wav_path)
                        
                except Exception as e:
                    print(f"[DEBUG] Error checking WAV format: {e}, proceeding with conversion")
                    convert_success = convert_m4a_to_wav(m4a_path, wav_path)
            else:
                # 다른 형식은 항상 변환
                convert_success = convert_m4a_to_wav(m4a_path, wav_path)
            
            if not convert_success:
                raise Exception("Audio conversion failed")

            # 무음 여부 확인
            if is_audio_silent(wav_path):
                os.remove(m4a_path)
                os.remove(wav_path)
                return Response({'message': '무음 파일은 삭제되었습니다.'}, status=400)

            # 성별 영어 → 한글 변환
            gender_mapping = {
                'male': '남',
                'female': '여',
                'Male': '남',
                'Female': '여',
                'MALE': '남',
                'FEMALE': '여',
                'M': '남',
                'F': '여',
                'm': '남',
                'f': '여'
            }
            if gender:
                gender = gender_mapping.get(gender, gender)

            # DB 저장 (카테고리 포함, audio_file 경로는 모델의 upload_to 함수가 처리)
            audio_record = AudioRecord.objects.create(
                audio_file=f'{category_folder}/{wav_filename}',  # 실제 저장된 파일명 사용
                category=category,
                identifier=identifier,
                # 공통 기본 정보
                name=name,
                gender=gender,
                age=age,
                birth_year=birth_year,
                birth_month=birth_month,
                birth_day=birth_day,
                # 녹음 환경 정보
                recording_location=place,  # place -> recording_location
                noise_level=noise,  # noise -> noise_level
                device_type=device,  # device -> device_type
                has_microphone=mic,  # mic -> has_microphone
                diagnosis=diagnosis,
                # SNR 정보
                snr_mean=float(snr_mean) if snr_mean else None,
                snr_max=float(snr_max) if snr_max else None,
                snr_min=float(snr_min) if snr_min else None,
                # 인덱스 컬럼 (쿼리 성능 최적화)
                region=region if region else None,
                education_level=int(final_education) if final_education and final_education.isdigit() else None,
                hearing_level=hearing_level if hearing_level else None,
                age_in_months=int(age_in_months) if age_in_months and str(age_in_months).isdigit() else None
            )
            
            # 카테고리별 특화 데이터 저장
            category_data = {}
            
            # 공통 작업 정보
            if region:
                category_data['region'] = region
            if pronun_problem:
                category_data['pronunciation_problem'] = pronun_problem
            if subjective_rating:
                category_data['subjective_rating'] = subjective_rating
            if sentence_index:
                category_data['sentence_index'] = sentence_index
            if sentence_text:
                category_data['sentence_text'] = sentence_text
            if task_type:
                category_data['task_type'] = task_type
            if upload_timestamp:
                category_data['upload_timestamp'] = upload_timestamp
            if local_saved:
                category_data['local_saved'] = local_saved
            if recording_date:
                category_data['recording_date'] = recording_date
            
            # 작업 특화 정보
            if retry_count:
                category_data['retry_count'] = retry_count
            if attempt:
                category_data['attempt'] = attempt
            if question_file:
                category_data['question_file'] = question_file
            if current_page:
                category_data['current_page'] = current_page
            if page_name:
                category_data['page_name'] = page_name
            
            # Child 고유 필드
            if category == 'child':
                if age_in_months:
                    category_data['age_in_months'] = age_in_months
            
            # Senior 고유 필드
            if category == 'senior':
                if education:
                    category_data['education'] = education
                if education_years:
                    category_data['education_years'] = education_years
                if final_education:
                    category_data['final_education'] = final_education
                if education_detail:
                    category_data['education_detail'] = education_detail
                if cognitive_decline:
                    category_data['cognitive_decline'] = cognitive_decline
                if subjective_score:
                    category_data['subjective_score'] = subjective_score
                if subjective_note:
                    category_data['subjective_note'] = subjective_note
                if job:
                    category_data['job'] = job
            
            # Auditory 고유 필드
            if category == 'auditory':
                # 교육 정보
                if education:
                    category_data['education'] = education
                if education_detail:
                    category_data['education_detail'] = education_detail
                if final_education:
                    category_data['final_education'] = final_education
                
                # 청각 관련
                if hearing_level:
                    category_data['hearing_level'] = hearing_level
                if hearing_loss_duration:
                    category_data['hearing_loss_duration'] = hearing_loss_duration
                if has_hearing_aid:
                    category_data['has_hearing_aid'] = has_hearing_aid
                if hearing_aid_duration:
                    category_data['hearing_aid_duration'] = hearing_aid_duration
                if hearing_onset_type:
                    category_data['hearing_onset_type'] = hearing_onset_type
                if hearing_impairment:
                    category_data['hearing_impairment'] = hearing_impairment
                
                # 인지 관련
                if cognitive_level:
                    category_data['cognitive_level'] = cognitive_level
                
                # 언어 관련
                if native_language:
                    category_data['native_language'] = native_language
                if language_experience:
                    category_data['language_experience'] = language_experience
                
                # 배경소음 측정
                if session_id:
                    category_data['session_id'] = session_id
                if background_noise_average:
                    category_data['background_noise_average'] = background_noise_average
                if background_noise_max:
                    category_data['background_noise_max'] = background_noise_max
                if background_noise_min:
                    category_data['background_noise_min'] = background_noise_min
                if noise_measurement_time:
                    category_data['noise_measurement_time'] = noise_measurement_time
                if platform:
                    category_data['platform'] = platform
                if age_in_months:
                    category_data['age_in_months'] = age_in_months
            
            # 메타데이터 JSON 저장
            if metadata_json:
                if isinstance(metadata_json, (dict, list)):
                    try:
                        category_data['metadata_json'] = json.dumps(metadata_json, ensure_ascii=False)
                    except Exception as e:
                        print(f"[DEBUG] Failed to serialize metadata_json dict: {e}")
                else:
                    category_data['metadata_json'] = str(metadata_json)
            if metadata_filename:
                category_data['metadata_filename'] = metadata_filename
                
            if category_data:
                audio_record.set_category_data(**category_data)
                audio_record.save()
                
            print(f"[DEBUG] Saved AudioRecord with ID: {audio_record.id}")
            print(f"[DEBUG] Category: {category}, Identifier: {identifier}")
            print(f"[DEBUG] Category specific data keys: {list(audio_record.category_specific_data.keys())}")
            print(f"[DEBUG] Category specific data count: {len(audio_record.category_specific_data)}")


            # 원본 파일 삭제 (WAV 파일이 아닌 경우만)
            if os.path.exists(m4a_path) and ext.lower() != 'wav':
                os.remove(m4a_path)
                print(f"[DEBUG] Removed original file: {m4a_path}")
            elif ext.lower() == 'wav':
                print(f"[DEBUG] Skipping removal of WAV file as it was converted in-place")

            return Response({
                'message': '업로드 성공',
                'file_path': audio_record.audio_file.url
            })
            
        except Exception as e:
            print(f"[ERROR] Upload failed: {str(e)}")
            
            # 손상된 파일 진단 정보 제공
            error_details = {'error': f'업로드 실패: {str(e)}'}
            if 'moov atom not found' in str(e):
                error_details.update({
                    'error_code': 'CORRUPTED_M4A_FILE',
                    'issue': 'M4A 파일 손상 (moov atom 누락)',
                    'description': 'M4A 파일의 메타데이터(moov atom)가 누락되어 변환할 수 없습니다.',
                    'cause': 'React Native MediaRecorder가 녹음을 완전히 완료하지 못했습니다.',
                    'solutions': [
                        '1. MediaRecorder 설정 변경: OutputFormat을 "wav"로 설정',
                        '2. 녹음 완료 후 MediaRecorder.stopRecorder() 호출 후 500ms 대기',
                        '3. MediaRecorder.release() 호출하여 리소스 해제',
                        '4. 파일 크기 검증: 최소 1KB 이상인지 확인',
                        '5. 앱 재시작 후 다시 녹음 시도'
                    ],
                    'react_native_fix': {
                        'recorder_options': {
                            'SampleRate': 16000,
                            'Channels': 1,
                            'AudioQuality': 'High',
                            'OutputFormat': 'wav',
                            'AudioEncoding': 'wav'
                        },
                        'proper_stop_sequence': [
                            'await AudioRecorderPlayer.stopRecorder()',
                            'await new Promise(resolve => setTimeout(resolve, 500))',
                            'await AudioRecorderPlayer.release()'
                        ]
                    },
                    'technical': 'Android MediaRecorder의 녹음 중단이나 불완전한 파일 생성으로 인한 문제. moov atom은 MP4/M4A 컨테이너의 메타데이터로, 녹음이 정상 완료되어야 생성됩니다.'
                })
            
            return Response(error_details, status=400)

def index(request):
    # 로그인된 사용자는 Tailwind 버전의 홈페이지를 보여줌
    if request.user.is_authenticated:
        return render(request, 'voice_app/index.html')
    
    return render(request, 'index.html')

def extract_metadata_to_fields(audio):
    """React Native 메타데이터에서 기본 필드로 정보 추출"""
    if not audio.category_specific_data or 'metadata_json' not in audio.category_specific_data:
        return
    
    try:
        import base64
        import json
        import binascii
        import re

        # Base64 디코딩 및 JSON 파싱 (안전한 처리)
        b64_data = audio.category_specific_data['metadata_json']

        if isinstance(b64_data, (dict, list)):
            metadata = b64_data
            print(f"[DEBUG] Direct dict/list metadata for audio {audio.id}")
        else:
            # 먼저 직접 JSON 파싱 시도 (Base64가 아닐 수도 있음)
            try:
                metadata = json.loads(b64_data)
                print(f"[DEBUG] Direct JSON parse successful for audio {audio.id}")
            except (json.JSONDecodeError, TypeError):
                # JSON이 아니면 Base64 디코딩 시도
                raw_str = str(b64_data)
                clean_b64 = re.sub(r'[^A-Za-z0-9+/=_-]', '', raw_str)
                clean_b64 = clean_b64.replace('-', '+').replace('_', '/')

                # 패딩 수정
                missing_padding = len(clean_b64) % 4
                if missing_padding:
                    clean_b64 += '=' * (4 - missing_padding)

                try:
                    decoded_bytes = base64.b64decode(clean_b64, validate=False)
                    decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
                    metadata = json.loads(decoded_str)
                    print(f"[DEBUG] Base64 decode successful for audio {audio.id}")
                except (base64.binascii.Error, binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as e:
                    print(f"[DEBUG] All decode methods failed for audio {audio.id}: {e}")
                    return
        
        # 메타데이터에서 기본 정보 추출
        metainfo_candidates = [
            metadata.get('metainfo_child', {}),
            metadata.get('metainfo_senior', {}),
            metadata.get('metainfo_old', {}),
            metadata.get('metainfo_adult', {}),
            metadata.get('metainfo', {}),
        ]

        for metainfo in metainfo_candidates:
            if not metainfo:
                continue
            if not audio.name and metainfo.get('name'):
                audio.name = metainfo.get('name')
            if not audio.gender and metainfo.get('gender'):
                audio.gender = metainfo.get('gender')
            if not audio.age and metainfo.get('age'):
                audio.age = metainfo.get('age')
            if not audio.recording_location and metainfo.get('place'):
                audio.recording_location = metainfo.get('place')
            if not audio.noise_level and metainfo.get('noise'):
                audio.noise_level = metainfo.get('noise')
            if not audio.device_type and metainfo.get('device'):
                audio.device_type = metainfo.get('device')
            if not audio.has_microphone and metainfo.get('mic'):
                audio.has_microphone = metainfo.get('mic')
            if not audio.diagnosis and metainfo.get('diagnosis'):
                audio.diagnosis = metainfo.get('diagnosis')
            
    except Exception as e:
        print(f"[DEBUG] Metadata extraction error for audio {audio.id}: {e}")

@login_required
def audio_list(request):
    # identifier 필터링 처리
    identifier_filter = request.GET.get('identifier', None)
    
    # 정렬 매개변수 처리
    sort_by = request.GET.get('sort', '-created_at')  # 기본값: 최신순
    valid_sort_fields = [
        'identifier', '-identifier',
        'id', '-id',
        'created_at', '-created_at',
        'name', '-name',
        'gender', '-gender',
        'age', '-age',
        'task_type', '-task_type',  # JSON 필드 내부 정렬 (Python에서 처리)
        'status', '-status',
        'category', '-category',
        'snr_mean', '-snr_mean',
        'snr_max', '-snr_max',
        'snr_min', '-snr_min',
        'region', '-region',
        'education_level', '-education_level',
        'hearing_level', '-hearing_level',
        'age_in_months', '-age_in_months'
    ]
    
    if sort_by not in valid_sort_fields:
        sort_by = '-created_at'
    
    # identifier 필터링 적용
    if identifier_filter:
        audio_list_qs = AudioRecord.objects.filter(identifier=identifier_filter)
    else:
        audio_list_qs = AudioRecord.objects.all()
    
    # task_type 정렬은 Python에서 처리
    if sort_by in ['task_type', '-task_type']:
        audio_list_qs = list(audio_list_qs)
        reverse = sort_by.startswith('-')
        audio_list_qs.sort(
            key=lambda x: x.category_specific_data.get('task_type', '') or '',
            reverse=reverse
        )
    else:
        audio_list_qs = audio_list_qs.order_by(sort_by)
    
    # 각 오디오에 대해 React Native 메타데이터에서 기본 정보 추출
    for audio in audio_list_qs:
        extract_metadata_to_fields(audio)
    
    paginator = Paginator(audio_list_qs, 10)  # 한 페이지당 10개 항목

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'voice_app/audio_list.html', {
        'page_obj': page_obj,
        'audios': page_obj.object_list,
        'current_sort': sort_by,
        'current_identifier': identifier_filter
    })

def category_audio_list(request, category):
    """카테고리별 오디오 리스트를 반환하는 뷰"""
    valid_categories = ['child', 'senior', 'atypical', 'auditory', 'normal']
    
    if category not in valid_categories:
        if (request.META.get('HTTP_ACCEPT', '').startswith('application/json') or 
            request.path.startswith('/api/')):
            return JsonResponse({'error': 'Invalid category'}, status=400)
        return redirect('audio_list')
    
    # identifier 필터링 처리
    identifier_filter = request.GET.get('identifier', None)
    
    # 정렬 매개변수 처리
    sort_by = request.GET.get('sort', '-created_at')  # 기본값: 최신순
    valid_sort_fields = [
        'identifier', '-identifier',
        'id', '-id',
        'created_at', '-created_at',
        'name', '-name',
        'gender', '-gender',
        'age', '-age',
        'task_type', '-task_type',  # JSON 필드 내부 정렬
        'status', '-status',
        'category', '-category',
        'snr_mean', '-snr_mean',
        'snr_max', '-snr_max',
        'snr_min', '-snr_min',
        'region', '-region',
        'education_level', '-education_level',
        'hearing_level', '-hearing_level',
        'age_in_months', '-age_in_months'
    ]
    
    if sort_by not in valid_sort_fields:
        sort_by = '-created_at'
    
    # identifier 필터링 적용
    if identifier_filter:
        audio_list_qs = AudioRecord.objects.filter(category=category, identifier=identifier_filter)
    else:
        audio_list_qs = AudioRecord.objects.filter(category=category)
    
    # task_type 정렬은 Python에서 처리
    if sort_by in ['task_type', '-task_type']:
        audio_list_qs = list(audio_list_qs)
        reverse = sort_by.startswith('-')
        audio_list_qs.sort(
            key=lambda x: x.category_specific_data.get('task_type', '') or '',
            reverse=reverse
        )
    else:
        audio_list_qs = audio_list_qs.order_by(sort_by)
    
    # 각 오디오에 대해 React Native 메타데이터에서 기본 정보 추출
    for audio in audio_list_qs:
        extract_metadata_to_fields(audio)
    
    paginator = Paginator(audio_list_qs, 10)  # 한 페이지당 10개 항목

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 카테고리 이름을 한글로 변환
    category_names = {
        'child': '아동',
        'senior': '노인', 
        'atypical': '음성 장애',
        'auditory': '청각 장애',  # 이 줄이 추가되어야 함
        'normal': '일반'
    }

    # React Native용 JSON 응답 또는 브라우저용 HTML 응답
    if (request.META.get('HTTP_ACCEPT', '').startswith('application/json') or 
        request.path.startswith('/api/')):
        # API 요청인 경우 JSON 반환
        audio_data = []
        for audio in page_obj.object_list:
            audio_data.append({
                'id': audio.id,
                'file_path': audio.audio_file.url if audio.audio_file else None,
                'category': audio.category,
                'gender': audio.gender,
                'age': audio.age,
                'created_at': audio.created_at.isoformat() if audio.created_at else None,
                'snr_mean': audio.snr_mean,
                'snr_max': audio.snr_max,
                'snr_min': audio.snr_min,
            })
        
        return JsonResponse({
            'audios': audio_data,
            'category': category,
            'category_name': category_names.get(category, category),
            'total_count': paginator.count,
            'page': page_obj.number,
            'total_pages': paginator.num_pages
        })
    
    # 브라우저 요청인 경우 HTML 템플릿 반환
    return render(request, 'voice_app/category_audio_list.html', {
        'page_obj': page_obj,
        'audios': page_obj.object_list,
        'category': category,
        'category_name': category_names.get(category, category),
        'current_sort': sort_by,
        'current_identifier': identifier_filter
    })


def delete_all_audios(request):
    if request.method == 'POST':
        audios = AudioRecord.objects.all()
        for record in audios:
            file_path = os.path.join(settings.MEDIA_ROOT, record.audio_file.name)
            if os.path.exists(file_path):
                os.remove(file_path)
            record.delete()
        return redirect('audio-list')
    else:
        return redirect('audio-list')

@require_POST
def update_transcription(request, audio_id):
    """수동 전사 내용 업데이트 (manual_transcript 필드)"""
    audio = get_object_or_404(AudioRecord, id=audio_id)
    new_manual_transcript = request.POST.get('manual_transcript', '').strip()

    if new_manual_transcript:
        audio.manual_transcript = new_manual_transcript
        audio.save()

    return redirect('audio_list')  # 템플릿에서 정의한 목록 뷰 이름

@csrf_exempt
def transcribe_unprocessed(request):
    if request.method == 'POST':
        model = whisper.load_model("base")  # 필요 시 small, medium 등 조정

        for record in AudioRecord.objects.filter(transcript__isnull=True):
            wav_path = os.path.join(settings.MEDIA_ROOT, str(record.audio_file))
            if os.path.exists(wav_path):
                try:
                    result = model.transcribe(wav_path, language='ko')
                    record.transcript = result['text']
                    # manual_transcript가 비어있으면 자동 전사 결과로 초기화
                    if not record.manual_transcript:
                        record.manual_transcript = result['text']
                    record.save()
                except Exception as e:
                    print(f"❌ 전사 실패 ({record.id}): {e}")
        return redirect('audio-list')
    else:
        return redirect('audio-list')

@csrf_exempt
def transcribe_single_audio(request, audio_id):
    audio = get_object_or_404(AudioRecord, id=audio_id)
    
    print(f"[Transcribe] Starting transcription for audio ID: {audio_id}")
    print(f"[Transcribe] Audio file path: {audio.audio_file.path if audio.audio_file else 'No file'}")

    if request.method == 'POST':
        # 오디오 파일 존재 여부 확인
        if not audio.audio_file:
            print(f"[Transcribe Error] No audio file for ID {audio_id}")
            messages.error(request, '오디오 파일이 없습니다.')
            return redirect('audio_detail', audio_id=audio_id)
        
        if not os.path.exists(audio.audio_file.path):
            print(f"[Transcribe Error] Audio file not found: {audio.audio_file.path}")
            messages.error(request, '오디오 파일을 찾을 수 없습니다.')
            return redirect('audio_detail', audio_id=audio_id)
        
        # 상태 업데이트 및 작업 시작
        audio.status = 'processing'
        audio.save()
        print(f"[Transcribe] Status set to 'processing' for audio ID: {audio_id}")
        
        try:
            # 직접 전사 실행 (동기 방식)
            print(f"[Transcribe] Calling transcribe_audio_task for ID: {audio_id}")
            transcribe_audio_task(audio.id)
            print(f"[Transcribe] Transcription task completed for ID: {audio_id}")
            
            # 결과 확인
            audio.refresh_from_db()
            if audio.transcript:
                print(f"[Transcribe Success] Transcription result: {audio.transcript[:100]}...")
                messages.success(request, 'Whisper 전사가 완료되었습니다.')
            else:
                print(f"[Transcribe Warning] No transcription result for ID: {audio_id}")
                messages.warning(request, '전사가 완료되었으나 결과가 없습니다.')
                
        except Exception as e:
            print(f"[Transcribe Error] Exception for ID {audio_id}: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            audio.status = 'failed'
            audio.save()
            messages.error(request, f'전사 중 오류가 발생했습니다: {str(e)}')
    
    # audio_detail 페이지로 리다이렉트
    return redirect('audio_detail', audio_id=audio_id)

@csrf_exempt
def reset_processing_status(request):
    if request.method == 'POST':
        AudioRecord.objects.filter(status='processing').update(status='failed')
        return redirect('audio_list')

@method_decorator(csrf_exempt, name='dispatch')
class SimpleCategoryUploadView(View):
    def get(self, request, category):
        """카테고리별 오디오 리스트 반환 (JSON)"""
        valid_categories = ['child', 'senior', 'atypical', 'auditory', 'normal']
        
        if category not in valid_categories:
            return JsonResponse({'error': '유효하지 않은 카테고리입니다.'}, status=400)
        
        audio_list = AudioRecord.objects.filter(category=category).order_by('-created_at')
        
        data = []
        for audio in audio_list:
            data.append({
                'id': audio.id,
                'audio_file': audio.audio_file.url if audio.audio_file else None,
                'category': audio.category,
                'gender': audio.gender,
                'age': audio.age,
                'transcript': audio.manual_transcript or audio.transcript,  # 수동 전사 우선, 없으면 자동 전사
                'status': audio.status,
                'snr_mean': audio.snr_mean,
                'snr_max': audio.snr_max,
                'snr_min': audio.snr_min,
                'created_at': audio.created_at.isoformat(),
                'detail_url': f'/audio/{audio.id}/',
                'web_detail_url': f'http://210.125.101.159:8001/audio/{audio.id}/'  # 8002 → 8001로 변경
            })
        
        return JsonResponse({
            'category': category,
            'count': len(data),
            'results': data
        })

    def post(self, request, category):
        """
        Handle file uploads for a specific category with conversion and folder structure.
        """
        valid_categories = ['child', 'senior', 'atypical', 'auditory', 'normal']

        if category not in valid_categories:
            return JsonResponse({'error': 'Invalid category.'}, status=400)

        if not request.FILES.get('file'):
            return JsonResponse({'error': 'No file provided.'}, status=400)

        file = request.FILES['file']
        gender = request.POST.get('gender', None)
        age = request.POST.get('age', None)
        
        # SNR 값들 추출
        snr_mean = request.POST.get('snr_mean')
        snr_max = request.POST.get('snr_max')
        snr_min = request.POST.get('snr_min')

        try:
            # 고유 파일명 생성
            ext = file.name.split('.')[-1]
            unique_id = uuid.uuid4().hex
            m4a_filename = f"{unique_id}.{ext}"
            
            # 카테고리별 저장 경로 생성
            category_folder = os.path.join('audio', category)
            m4a_storage_path = os.path.join(category_folder, m4a_filename)

            # 카테고리 폴더가 없으면 생성
            category_media_folder = os.path.join(settings.MEDIA_ROOT, category_folder)
            os.makedirs(category_media_folder, exist_ok=True)

            # m4a 파일 저장
            file_data = ContentFile(file.read())
            m4a_full_path = default_storage.save(m4a_storage_path, file_data)
            m4a_path = os.path.join(settings.MEDIA_ROOT, m4a_full_path)

            # wav 변환 경로 지정 (카테고리별 폴더에 저장)
            wav_filename = f"{unique_id}.wav"
            wav_path = os.path.join(settings.MEDIA_ROOT, category_folder, wav_filename)

            # 변환 실행
            convert_m4a_to_wav(m4a_path, wav_path)

            # 무음 여부 확인
            if is_audio_silent(wav_path):
                os.remove(m4a_path)
                os.remove(wav_path)
                return JsonResponse({'error': 'Silent file was rejected.'}, status=400)

            # DB 저장 (카테고리 포함, audio_file 경로는 카테고리별 경로)
            audio_record = AudioRecord.objects.create(
                audio_file=f'{category_folder}/{wav_filename}',  # 카테고리별 경로
                category=category,
                gender=gender,
                age=age,
                snr_mean=float(snr_mean) if snr_mean else None,
                snr_max=float(snr_max) if snr_max else None,
                snr_min=float(snr_min) if snr_min else None
            )

            # m4a 삭제
            if os.path.exists(m4a_path):
                os.remove(m4a_path)

            return JsonResponse({
                'message': 'File uploaded successfully.',
                'id': audio_record.id,
                'file_path': audio_record.audio_file.url,
                'category': category
            }, status=201)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def api_all_audio_list(request):
    """React Native를 위한 전체 오디오 리스트 API"""
    audio_list = AudioRecord.objects.all().order_by('-created_at')
    
    data = []
    for audio in audio_list:
        data.append({
            'id': audio.id,
            'audio_file': audio.audio_file.url if audio.audio_file else None,
            'category': audio.category,
            'gender': audio.gender,
            'age': audio.age,
            'transcript': audio.manual_transcript or audio.transcript,  # 수동 전사 우선
            'status': audio.status,
            'snr_mean': audio.snr_mean,
            'snr_max': audio.snr_max,
            'snr_min': audio.snr_min,
            'created_at': audio.created_at.isoformat(),
            'detail_url': f'/audio/{audio.id}/',
            'web_detail_url': f'http://210.125.101.159:8001/audio/{audio.id}/'  # 8002 → 8001로 변경
        })
    
    return Response({
        'count': len(data),
        'results': data
    })

@csrf_exempt
def django_upload(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        gender = request.POST.get('gender', 'unknown')
        age = request.POST.get('age', 'unknown')

        if not file:
            return JsonResponse({'success': False, 'error': '파일이 없습니다.'}, status=400)

        # 파일 저장 경로 설정
        file_path = os.path.join(settings.MEDIA_ROOT, 'audio', file.name)
        with open(file_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)

        return JsonResponse({'success': True, 'message': '파일 업로드 성공', 'file_path': file_path})

    return JsonResponse({'success': False, 'error': '잘못된 요청입니다.'}, status=405)

@api_view(['GET', 'PUT', 'PATCH'])
def api_audio_detail(request, audio_id):
    """개별 오디오 파일의 상세 정보를 조회하고 편집하는 API"""
    try:
        audio = AudioRecord.objects.get(id=audio_id)
    except AudioRecord.DoesNotExist:
        return Response({'error': '오디오 파일을 찾을 수 없습니다.'}, status=404)
    
    if request.method == 'GET':
        data = {
            'id': audio.id,
            'audio_file': audio.audio_file.url if audio.audio_file else None,
            'category': audio.category,
            'gender': audio.gender,
            'age': audio.age,
            'transcript': audio.manual_transcript or audio.transcript,  # 수동 전사 우선
            'auto_transcript': audio.transcript,  # 자동 전사 (원본)
            'manual_transcript': audio.manual_transcript,  # 수동 전사
            'status': audio.status,
            'snr_mean': audio.snr_mean,
            'snr_max': audio.snr_max,
            'snr_min': audio.snr_min,
            'created_at': audio.created_at.isoformat(),
            'detail_url': f'/audio/{audio.id}/',
            'web_detail_url': f'http://210.125.101.159:8001/audio/{audio.id}/'  # 8002 → 8001로 변경
        }
        return Response(data)
    
    elif request.method in ['PUT', 'PATCH']:
        # 개별 오디오 파일 정보 편집
        data = request.data
        
        # 수정 가능한 필드들
        if 'gender' in data:
            audio.gender = data['gender']
        if 'age' in data:
            audio.age = data['age']
        if 'manual_transcript' in data:
            audio.manual_transcript = data['manual_transcript']
        if 'category' in data:
            valid_categories = ['child', 'senior', 'atypical', 'auditory', 'normal']
            if data['category'] in valid_categories:
                audio.category = data['category']
        if 'snr_mean' in data:
            audio.snr_mean = float(data['snr_mean']) if data['snr_mean'] else None
        if 'snr_max' in data:
            audio.snr_max = float(data['snr_max']) if data['snr_max'] else None
        if 'snr_min' in data:
            audio.snr_min = float(data['snr_min']) if data['snr_min'] else None
        
        audio.save()
        
        # 업데이트된 정보 반환
        response_data = {
            'id': audio.id,
            'audio_file': audio.audio_file.url if audio.audio_file else None,
            'category': audio.category,
            'gender': audio.gender,
            'age': audio.age,
            'transcript': audio.manual_transcript or audio.transcript,  # 수동 전사 우선
            'auto_transcript': audio.transcript,
            'manual_transcript': audio.manual_transcript,
            'status': audio.status,
            'snr_mean': audio.snr_mean,
            'snr_max': audio.snr_max,
            'snr_min': audio.snr_min,
            'created_at': audio.created_at.isoformat()
        }
        return Response({
            'message': '오디오 파일 정보가 성공적으로 업데이트되었습니다.',
            'data': response_data
        })

@login_required
def audio_detail(request, audio_id):
    """개별 오디오 파일의 상세 정보를 표시하는 뷰"""
    audio = get_object_or_404(AudioRecord, id=audio_id)
    
    # 카테고리 한글명 매핑
    category_names = {
        'child': '아동',
        'senior': '노인',
        'atypical': '음성 장애',
        'auditory': '청각 장애',
        'normal': '일반'
    }
    
    # JSON 메타데이터에서 실제 데이터 추출
    category_data = audio.category_specific_data or {}
    metadata_json_str = category_data.get('metadata_json', '')
    
    # 안전한 메타데이터 파싱
    actual_metadata = {}
    if metadata_json_str:
        try:
            # 먼저 직접 JSON 파싱 시도
            try:
                actual_metadata = json.loads(metadata_json_str)
                print(f"[DEBUG] Direct JSON parse successful: {actual_metadata}")
            except (json.JSONDecodeError, TypeError):
                # Base64 디코딩 시도
                # Base64 문자열 정리
                clean_b64 = ''.join(c for c in str(metadata_json_str) if c.isalnum() or c in '+/=')
                
                # 패딩 수정
                missing_padding = len(clean_b64) % 4
                if missing_padding:
                    clean_b64 += '=' * (4 - missing_padding)
                
                decoded_bytes = base64.b64decode(clean_b64, validate=True)
                decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
                actual_metadata = json.loads(decoded_str)
                print(f"[DEBUG] Base64 decode successful: {actual_metadata}")
        except Exception as e:
            print(f"[DEBUG] All metadata decode methods failed: {e}")
            actual_metadata = {}
    
    # 실제 메타데이터에서 필드 추출
    metainfo_child = actual_metadata.get('metainfo_child', {})
    metainfo_senior = actual_metadata.get('metainfo_senior', {}) or actual_metadata.get('metainfo_old', {})
    task_info = actual_metadata.get('task_info', {})
    upload_info = actual_metadata.get('upload_info', {})
    
    # 생년월일 조합
    birth_date = None
    if audio.birth_year and audio.birth_month and audio.birth_day:
        birth_date = f"{audio.birth_year}-{audio.birth_month.zfill(2)}-{audio.birth_day.zfill(2)}"
    elif metainfo_child.get('birthDate'):
        birth_date = metainfo_child.get('birthDate')
    
    # JSON 데이터를 문자열로 변환
    category_data_json = json.dumps(audio.category_specific_data or {})
    alignment_data_json = json.dumps(audio.alignment_data or {})
    
    # 카테고리별 필드 스키마 정보
    category_schema = {
        'child': {
            'place': '녹음 장소',
            'pronunciation_problem': '발음 문제',
            'region': '지역',
            'sentence_index': '문장 번호',
            'sentence_text': '문장 내용',
            'task_type': '과제 유형',
            'subjective_rating': '주관적 평가',
            'recording_date': '녹음 날짜',
            'upload_timestamp': '업로드 시간'
        },
        'senior': {
            'education': '교육 수준',
            'has_voice_problem': '음성 문제 여부',
            'region': '지역'
        },
        'auditory': {
            'education': '교육 수준',
            'hearing_level': '청각 수준',
            'hearing_loss_duration': '청각 손실 기간',
            'has_hearing_aid': '보청기 착용',
            'cognitive_level': '인지 수준',
            'region': '지역',
            'has_voice_problem': '음성 문제 여부'
        }
    }
    
    # 통합된 메타데이터 필드들 (카테고리별 실제 데이터 우선)
    if audio.category == 'child':
        integrated_metadata = {
            'name': metainfo_child.get('name') or audio.name or '',
            'gender': metainfo_child.get('gender') or audio.gender or '',
            'age': metainfo_child.get('age') or audio.age or '',
            'birth_date': birth_date or '',
            'recording_location': metainfo_child.get('place') or audio.recording_location or '',
            'region': metainfo_child.get('region') or '',
            'noise_level': metainfo_child.get('noise') or audio.noise_level or '',
            'device_type': metainfo_child.get('device') or audio.device_type or '',
            'has_microphone': metainfo_child.get('mic') or audio.has_microphone or '',
            'diagnosis': metainfo_child.get('diagnosis') or audio.diagnosis or '',
            'task_type': task_info.get('task_type', ''),
            'sentence_text': task_info.get('sentence_text', ''),
            'sentence_index': task_info.get('sentence_index', ''),
            'recording_date': metainfo_child.get('recordingDate') or upload_info.get('recording_timestamp', ''),
            'upload_timestamp': upload_info.get('upload_timestamp', ''),
            'subjective_rating': upload_info.get('subjective_rating', ''),
            'audio_filename': upload_info.get('audio_filename', ''),
        }
    elif audio.category == 'senior':
        integrated_metadata = {
            'name': metainfo_senior.get('name') or audio.name or '',
            'gender': metainfo_senior.get('gender') or audio.gender or '',
            'age': metainfo_senior.get('age') or audio.age or '',
            'birth_date': metainfo_senior.get('birthDate') or birth_date or '',
            'recording_location': metainfo_senior.get('recordingLocation') or audio.recording_location or '',
            'region': metainfo_senior.get('region') or '',
            'noise_level': metainfo_senior.get('noiseLevel') or metainfo_senior.get('noise') or audio.noise_level or '',
            'device_type': metainfo_senior.get('deviceType') or metainfo_senior.get('device') or audio.device_type or '',
            'has_microphone': metainfo_senior.get('hasMicrophone') or metainfo_senior.get('mic') or audio.has_microphone or '',
            'diagnosis': metainfo_senior.get('diagnosis') or audio.diagnosis or '',
            'task_type': task_info.get('task_type', ''),
            'sentence_text': task_info.get('sentence_text', ''),
            'sentence_index': task_info.get('sentence_index', ''),
            'recording_date': metainfo_senior.get('recordingDate') or upload_info.get('recording_timestamp', ''),
            'upload_timestamp': upload_info.get('upload_timestamp', ''),
            'subjective_rating': upload_info.get('subjective_rating', '') or metainfo_senior.get('subjectiveScore', ''),
            'audio_filename': upload_info.get('audio_filename', ''),
        }
    else:
        # 기타 카테고리는 기존 기본값 위주
        integrated_metadata = {
            'identifier': audio.identifier or '',
            'name': audio.name or '',
            'gender': audio.gender or '',
            'age': audio.age or '',
            'birth_date': birth_date or '',
            'recording_location': audio.recording_location or '',
            'region': '',
            'noise_level': audio.noise_level or '',
            'device_type': audio.device_type or '',
            'has_microphone': audio.has_microphone or '',
            'diagnosis': audio.diagnosis or '',
            'task_type': task_info.get('task_type', ''),
            'sentence_text': task_info.get('sentence_text', ''),
            'sentence_index': task_info.get('sentence_index', ''),
            'recording_date': upload_info.get('recording_timestamp', ''),
            'upload_timestamp': upload_info.get('upload_timestamp', ''),
            'subjective_rating': upload_info.get('subjective_rating', ''),
            'audio_filename': upload_info.get('audio_filename', ''),
        }
    
    # 카테고리별 데이터 디스플레이 (실제 메타데이터 우선)
    category_display = {}
    if audio.category == 'child':
        category_display = {
            'place': metainfo_child.get('place', ''),
            'region': metainfo_child.get('region', ''),
            'pronunciation_problem': metainfo_child.get('pronunProblem', ''),
            'subjective_rating': upload_info.get('subjective_rating', ''),
            'sentence_index': task_info.get('sentence_index', ''),
            'sentence_text': task_info.get('sentence_text', ''),
            'task_type': task_info.get('task_type', ''),
            'recording_date': metainfo_child.get('recordingDate', ''),
            'upload_timestamp': upload_info.get('upload_timestamp', ''),
            'audio_filename': upload_info.get('audio_filename', ''),
        }
    elif audio.category == 'senior':
        category_display = {
            'region': metainfo_senior.get('region', ''),
            'recording_location': metainfo_senior.get('recordingLocation', ''),
            'noise_level': metainfo_senior.get('noiseLevel', '') or metainfo_senior.get('noise', ''),
            'device_type': metainfo_senior.get('deviceType', '') or metainfo_senior.get('device', ''),
            'has_voice_problem': metainfo_senior.get('hasVoiceProblem', ''),
            'has_microphone': metainfo_senior.get('hasMicrophone', '') or metainfo_senior.get('mic', ''),
            'education': metainfo_senior.get('education', ''),
            'diagnosis': metainfo_senior.get('diagnosis', ''),
            'recording_date': metainfo_senior.get('recordingDate', ''),
            'upload_timestamp': upload_info.get('upload_timestamp', ''),
            'audio_filename': upload_info.get('audio_filename', ''),
        }
    
    context = {
        'audio': audio,
        'user': request.user,  # user 컨텍스트 추가
        'category_name': category_names.get(audio.category, audio.category),
        'birth_date': birth_date,
        'category_data_json': category_data_json,
        'alignment_data_json': alignment_data_json,
        'category_schema': category_schema.get(audio.category, {}),
        'has_category_data': bool(audio.category_specific_data),
        'has_alignment_data': bool(audio.alignment_data),
        
        # 통합된 메타데이터 필드들
        'metadata_fields': integrated_metadata,
        
        # 상태 정보
        'status_info': {
            'transcription_status': audio.status,
            'alignment_status': getattr(audio, 'alignment_status', 'pending'),
            'has_transcript': bool(audio.transcript),  # transcript 필드명 수정
            'has_manual_transcript': bool(audio.manual_transcript),
        },
        
        # 카테고리별 데이터 (실제 메타데이터 우선)
        'category_data_display': category_display,
        
        # 디버깅용 원본 데이터
        'raw_metadata': actual_metadata,
        'metainfo_child': metainfo_child,
        'task_info': task_info,
        'upload_info': upload_info,
    }
    
    return render(request, 'voice_app/audio_detail.html', context)

@require_POST
def update_audio_metadata(request, audio_id):
    """오디오 파일의 메타 정보를 업데이트하는 뷰"""
    audio = get_object_or_404(AudioRecord, id=audio_id)
    
    # 성별 영어 → 한글 변환 매핑
    gender_mapping = {
        'male': '남',
        'female': '여',
        'Male': '남',
        'Female': '여',
        'MALE': '남',
        'FEMALE': '여',
        'M': '남',
        'F': '여',
        'm': '남',
        'f': '여'
    }
    
    # 폼 데이터 가져오기
    gender = request.POST.get('gender', '').strip()
    age = request.POST.get('age', '').strip()
    category = request.POST.get('category', '').strip()
    snr_mean = request.POST.get('snr_mean', '').strip()
    snr_max = request.POST.get('snr_max', '').strip()
    snr_min = request.POST.get('snr_min', '').strip()
    
    # 데이터 업데이트
    if gender:
        # 성별을 한글로 변환
        audio.gender = gender_mapping.get(gender, gender)
    if age:
        audio.age = age
    if category:
        valid_categories = ['child', 'senior', 'atypical', 'auditory', 'normal']
        if category in valid_categories:
            audio.category = category
    
    # SNR 값들 업데이트
    audio.snr_mean = float(snr_mean) if snr_mean else None
    audio.snr_max = float(snr_max) if snr_max else None
    audio.snr_min = float(snr_min) if snr_min else None
    
    audio.save()
    
    return redirect('audio_detail', audio_id=audio_id)

# WhisperX 관련 기능 추가 - 의존성 때문에 임시 주석
# import whisperx
import tempfile
# import torch

# WhisperX 의존성 때문에 임시 주석처리
"""
class WhisperXProcessor:
    # WhisperX를 관리하는 최적화된 클래스
    def __init__(self, model_size="base", device="auto"):
        self.model_size = model_size
        self.device = self._get_best_device(device)
        self.compute_type = "int8" if self.device == "cpu" else "float16"
        self.model = None
        self.alignment_models = {}
    
    def _get_best_device(self, device):
        # 최적의 디바이스 선택
        if device == "auto":
            if torch.cuda.is_available():
                try:
                    # CUDA 테스트
                    test_tensor = torch.tensor([1.0]).cuda()
                    return "cuda"
                except:
                    return "cpu"
            else:
                return "cpu"
        return device
    
    def load_model(self):
        # ASR 모델 로드 (싱글톤)
        if self.model is None:
            try:
                self.model = whisperx.load_model(
                    self.model_size, 
                    device=self.device,
                    compute_type=self.compute_type
                )
                print(f"✅ WhisperX 모델 로드 완료: {self.model_size} ({self.device})")
            except Exception as e:
                print(f"❌ WhisperX 모델 로드 실패: {e}")
                # CPU fallback
                if self.device == "cuda":
                    self.device = "cpu"
                    self.compute_type = "int8"
                    self.model = whisperx.load_model(
                        self.model_size, 
                        device="cpu",
                        compute_type="int8"
                    )
                else:
                    raise e
        return self.model
    
    def get_alignment_model(self, language_code):
        # 언어별 정렬 모델 로드 (캐싱)
        if language_code not in self.alignment_models:
            try:
                alignment_model, metadata = whisperx.load_align_model(
                    language_code=language_code, 
                    device=self.device
                )
                self.alignment_models[language_code] = (alignment_model, metadata)
                print(f"✅ 정렬 모델 로드 완료: {language_code}")
            except Exception as e:
                print(f"❌ 정렬 모델 로드 실패 ({language_code}): {e}")
                raise e
        return self.alignment_models[language_code]
    
    def transcribe_with_alignment(self, audio_path, **kwargs):
        # 음성인식 + 정렬을 한번에 수행
        try:
            # ASR 수행
            model = self.load_model()
            
            # 설정값들
            batch_size = kwargs.get('batch_size', 16)
            temperature = kwargs.get('temperature', 0.0)
            language = kwargs.get('language')
            
            asr_options = {
                'batch_size': batch_size,
                'temperature': temperature,
            }
            if language:
                asr_options['language'] = language
                
            result = model.transcribe(audio_path, **asr_options)
            
            # 언어 감지 결과
            detected_language = result.get("language", "en")
            
            # 정렬 수행 (단어 단위 타이밍)
            try:
                alignment_model, metadata = self.get_alignment_model(detected_language)
                aligned_result = whisperx.align(
                    result["segments"], 
                    alignment_model, 
                    metadata, 
                    audio_path, 
                    device=self.device,
                    return_char_alignments=False
                )
                segments = aligned_result.get("segments", [])
            except Exception as e:
                print(f"⚠ 정렬 실패, ASR 결과만 사용: {e}")
                segments = result.get("segments", [])
            
            # 전체 텍스트 생성
            full_text = " ".join([segment.get("text", "") for segment in segments])
            
            return {
                'success': True,
                'language': detected_language,
                'text': full_text,
                'segments': segments,
                'segment_count': len(segments),
                'processing_info': {
                    'model_size': self.model_size,
                    'device': self.device,
                    'compute_type': self.compute_type
                }
            }
            
        except Exception as e:
            print(f"❌ WhisperX 처리 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }

# 전역 WhisperX 프로세서 인스턴스
whisperx_processor = WhisperXProcessor(model_size="base", device="auto")
"""

@csrf_exempt
@api_view(['POST'])
def whisperx_transcribe(request):
    """
    WhisperX를 사용한 고급 음성인식 API (임시 비활성화)
    """
    return Response({
        'error': 'WhisperX service is temporarily unavailable',
        'message': 'whisperx 의존성이 설치되지 않았습니다.'
    }, status=503)

@csrf_exempt
@api_view(['POST'])
def whisperx_transcribe_simple(request):
    """
    WhisperX 간단한 음성인식 API (임시 비활성화)
    """
    return Response({
        'error': 'WhisperX service is temporarily unavailable',
        'message': 'whisperx 의존성이 설치되지 않았습니다.'
    }, status=503)


def dashboard(request):
    """데이터 대시보드 페이지 - Identifier 기반 화자 그룹핑 통계 (로그인 불필요)"""
    from django.db.models import Count, Avg, Max, Min, Q, F
    import json
    from collections import defaultdict
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # === 전체 통계 ===
    total_files = AudioRecord.objects.count()
    
    # === Identifier 기반 화자(Speaker) 통계 ===
    # 각 identifier는 하나의 고유한 화자를 나타냄
    unique_speakers = AudioRecord.objects.exclude(identifier__isnull=True).exclude(identifier__exact='').values('identifier').distinct()
    total_speakers = unique_speakers.count()
    
    # 화자별 정보 수집 (identifier로 그룹핑)
    speaker_info = {}
    speaker_recordings_count = defaultdict(int)
    
    for speaker in unique_speakers:
        identifier = speaker['identifier']
        # 해당 화자의 첫 번째 레코드에서 메타데이터 추출 (같은 identifier는 동일한 화자 정보를 가짐)
        first_record = AudioRecord.objects.filter(identifier=identifier).first()
        
        if first_record:
            category = first_record.category
            speaker_info[identifier] = {
                'identifier': identifier,
                'category': category,
                'gender': first_record.gender,
                'region': first_record.region,
                'education_level': first_record.education_level,
                'hearing_level': first_record.hearing_level,
                'age_in_months': first_record.age_in_months,
                'recordings_count': AudioRecord.objects.filter(identifier=identifier).count()
            }
            
            # 카테고리별 추가 정보
            if category == 'child':
                speaker_info[identifier]['age_group'] = f"{(first_record.age_in_months // 12)}세" if first_record.age_in_months else None
                speaker_info[identifier]['device'] = first_record.get_category_data('device')
                speaker_info[identifier]['task_type'] = first_record.get_category_data('task_type')
            
            elif category == 'senior':
                # 연령은 metadata에 있음
                age = first_record.get_category_data('age')
                speaker_info[identifier]['age'] = age
                speaker_info[identifier]['cognitive_decline'] = first_record.get_category_data('cognitive_decline')
                speaker_info[identifier]['job'] = first_record.get_category_data('job')
            
            elif category == 'auditory':
                age = first_record.get_category_data('age')
                speaker_info[identifier]['age'] = age
                speaker_info[identifier]['has_hearing_aid'] = first_record.get_category_data('has_hearing_aid')
                speaker_info[identifier]['native_language'] = first_record.get_category_data('native_language')
    
    # 카테고리별 화자 수 통계
    category_speaker_stats = defaultdict(int)
    for info in speaker_info.values():
        category_speaker_stats[info['category']] += 1
    
    category_speaker_stats_list = [{'category': k, 'count': v} for k, v in category_speaker_stats.items()]
    
    # 성별 화자 수 통계
    gender_speaker_stats = defaultdict(int)
    for info in speaker_info.values():
        if info['gender']:
            gender_speaker_stats[info['gender']] += 1
    
    gender_speaker_stats_list = [{'gender': k, 'count': v} for k, v in gender_speaker_stats.items()]
    
    # 지역별 화자 수 통계
    region_speaker_stats = defaultdict(int)
    for info in speaker_info.values():
        if info['region']:
            region_speaker_stats[info['region']] += 1
    
    region_speaker_stats_list = sorted([{'region': k, 'count': v} for k, v in region_speaker_stats.items()], key=lambda x: x['count'], reverse=True)
    
    # 교육 수준별 화자 수 통계 (Senior, Auditory)
    education_speaker_stats = defaultdict(int)
    for info in speaker_info.values():
        if info['category'] in ['senior', 'auditory'] and info.get('education_level'):
            education_speaker_stats[info['education_level']] += 1
    
    education_speaker_stats_list = sorted([{'education_level': k, 'count': v} for k, v in education_speaker_stats.items()], key=lambda x: x['education_level'])
    
    # 청력 수준별 화자 수 통계 (Auditory)
    hearing_speaker_stats = defaultdict(int)
    for info in speaker_info.values():
        if info['category'] == 'auditory' and info.get('hearing_level'):
            hearing_speaker_stats[info['hearing_level']] += 1
    
    hearing_speaker_stats_list = sorted([{'hearing_level': k, 'count': v} for k, v in hearing_speaker_stats.items()], key=lambda x: x['hearing_level'])
    
    # 연령대별 화자 수 통계 (Child)
    age_group_speaker_stats = defaultdict(int)
    for info in speaker_info.values():
        if info['category'] == 'child' and info.get('age_group'):
            age_group_speaker_stats[info['age_group']] += 1
    
    age_group_speaker_stats_list = sorted([{'age_group': k, 'count': v} for k, v in age_group_speaker_stats.items()], key=lambda x: x['age_group'])
    
    # === 기존 파일 기반 통계 (참고용) ===
    # 카테고리별 통계
    category_stats = list(AudioRecord.objects.values('category').annotate(count=Count('id')).order_by('category'))
    
    # 성별 통계
    gender_stats = list(AudioRecord.objects.exclude(gender__isnull=True).exclude(gender__exact='').values('gender').annotate(count=Count('id')).order_by('gender'))
    
    # 상태별 통계
    status_stats = list(AudioRecord.objects.values('status').annotate(count=Count('id')).order_by('status'))
    
    # SNR 통계
    snr_stats = AudioRecord.objects.exclude(snr_mean__isnull=True).aggregate(
        avg_snr=Avg('snr_mean'),
        max_snr=Max('snr_mean'),
        min_snr=Min('snr_mean'),
        count_with_snr=Count('snr_mean')
    )
    
    # 월별 업로드 통계 (최근 12개월)
    monthly_stats = []
    for i in range(12):
        month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
        month_end = month_start + timedelta(days=32)
        month_end = month_end.replace(day=1) - timedelta(days=1)
        
        count = AudioRecord.objects.filter(
            created_at__gte=month_start,
            created_at__lte=month_end
        ).count()
        
        monthly_stats.append({
            'month': month_start.strftime('%Y-%m'),
            'count': count
        })
    
    monthly_stats.reverse()  # 시간순 정렬
    
    # === 카테고리별 상세 화자 통계 ===
    
    # Child 화자 통계
    child_speakers = [info for info in speaker_info.values() if info['category'] == 'child']
    child_device_stats = defaultdict(int)
    child_task_stats = defaultdict(int)
    
    for speaker in child_speakers:
        if speaker.get('device'):
            child_device_stats[speaker['device']] += 1
        if speaker.get('task_type'):
            child_task_stats[speaker['task_type']] += 1
    
    # Senior 화자 통계
    senior_speakers = [info for info in speaker_info.values() if info['category'] == 'senior']
    senior_cognitive_stats = defaultdict(int)
    senior_job_stats = defaultdict(int)
    
    for speaker in senior_speakers:
        if speaker.get('cognitive_decline'):
            senior_cognitive_stats[speaker['cognitive_decline']] += 1
        if speaker.get('job'):
            senior_job_stats[speaker['job']] += 1
    
    # Auditory 화자 통계
    auditory_speakers = [info for info in speaker_info.values() if info['category'] == 'auditory']
    auditory_hearing_aid_stats = defaultdict(int)
    auditory_language_stats = defaultdict(int)
    
    for speaker in auditory_speakers:
        if speaker.get('has_hearing_aid'):
            auditory_hearing_aid_stats[speaker['has_hearing_aid']] += 1
        if speaker.get('native_language'):
            auditory_language_stats[speaker['native_language']] += 1
    
    # 리스트로 변환
    child_device_stats_list = sorted([{'device': k, 'count': v} for k, v in child_device_stats.items()], key=lambda x: x['count'], reverse=True)
    child_task_stats_list = sorted([{'task': k, 'count': v} for k, v in child_task_stats.items()], key=lambda x: x['count'], reverse=True)
    senior_cognitive_stats_list = [{'status': k, 'count': v} for k, v in senior_cognitive_stats.items()]
    senior_job_stats_list = sorted([{'job': k, 'count': v} for k, v in senior_job_stats.items()], key=lambda x: x['count'], reverse=True)[:10]
    auditory_hearing_aid_stats_list = [{'status': k, 'count': v} for k, v in auditory_hearing_aid_stats.items()]
    auditory_language_stats_list = sorted([{'language': k, 'count': v} for k, v in auditory_language_stats.items()], key=lambda x: x['count'], reverse=True)
    
    # === 화자별 녹음 수 분포 ===
    recordings_per_speaker = defaultdict(int)
    for info in speaker_info.values():
        count = info['recordings_count']
        if count == 1:
            recordings_per_speaker['1개'] += 1
        elif count <= 5:
            recordings_per_speaker['2-5개'] += 1
        elif count <= 10:
            recordings_per_speaker['6-10개'] += 1
        elif count <= 20:
            recordings_per_speaker['11-20개'] += 1
        else:
            recordings_per_speaker['21개 이상'] += 1
    
    recordings_per_speaker_list = [{'range': k, 'count': v} for k, v in recordings_per_speaker.items()]
    
    # 화자당 평균 녹음 수
    avg_recordings_per_speaker = total_files / total_speakers if total_speakers > 0 else 0
    
    # === 진단명 통계 (파일 기반) ===
    diagnosis_stats = list(
        AudioRecord.objects.exclude(diagnosis__isnull=True).exclude(diagnosis__exact='')
        .values('diagnosis')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    
    context = {
        # 전체 통계
        'total_files': total_files,
        'total_speakers': total_speakers,
        'avg_recordings_per_speaker': round(avg_recordings_per_speaker, 1),
        
        # 화자(Speaker) 기반 통계
        'category_speaker_stats': category_speaker_stats_list,
        'gender_speaker_stats': gender_speaker_stats_list,
        'region_speaker_stats': region_speaker_stats_list,
        'education_speaker_stats': education_speaker_stats_list,
        'hearing_speaker_stats': hearing_speaker_stats_list,
        'age_group_speaker_stats': age_group_speaker_stats_list,
        
        # 화자별 녹음 수 분포
        'recordings_per_speaker': recordings_per_speaker_list,
        
        # 카테고리별 화자 상세 통계
        'child_device_stats': child_device_stats_list,
        'child_task_stats': child_task_stats_list,
        'senior_cognitive_stats': senior_cognitive_stats_list,
        'senior_job_stats': senior_job_stats_list,
        'auditory_hearing_aid_stats': auditory_hearing_aid_stats_list,
        'auditory_language_stats': auditory_language_stats_list,
        
        # 파일 기반 통계 (참고용)
        'category_stats': category_stats,
        'gender_stats': gender_stats,
        'status_stats': status_stats,
        'snr_stats': snr_stats,
        'monthly_stats': monthly_stats,
        'diagnosis_stats': diagnosis_stats,
    }
    
    return render(request, 'voice_app/dashboard.html', context)



# WhisperX Alignment 관련 뷰들
@login_required
@require_POST
def whisperx_align_audio(request, audio_id):
    """
    WhisperX를 사용하여 오디오 파일의 forced alignment 수행
    """
    try:
        audio_record = get_object_or_404(AudioRecord, id=audio_id)
        
        if audio_record.alignment_status == 'processing':
            messages.warning(request, '이미 처리 중인 파일입니다.')
            return redirect('audio_detail', audio_id=audio_id)
        
        # 상태를 처리 중으로 변경
        audio_record.alignment_status = 'processing'
        audio_record.save()
        
        messages.info(request, 'WhisperX alignment 처리를 시작합니다. 잠시만 기다려주세요.')
        
        # 오디오 파일 경로
        audio_path = audio_record.audio_file.path
        
        # WhisperX 처리 수행
        result = transcribe_and_align_whisperx(audio_path)
        
        if result['success']:
            # 성공한 경우
            audio_record.alignment_data = {
                'segments': result['segments'],
                'word_segments': result['word_segments'],
                'transcription': result['transcription'],
                'success': True
            }
            audio_record.alignment_status = 'completed'
            
            # 전사가 없었다면 전사도 업데이트
            if not audio_record.transcript:
                audio_record.transcript = result['transcription']
                # manual_transcript가 비어있으면 자동 전사 결과로 초기화
                if not audio_record.manual_transcript:
                    audio_record.manual_transcript = result['transcription']
                audio_record.status = 'completed'
            
            audio_record.save()
            messages.success(request, 'WhisperX alignment가 완료되었습니다!')
        else:
            # 실패한 경우
            audio_record.alignment_data = {
                'error': result['error'],
                'success': False
            }
            audio_record.alignment_status = 'failed'
            audio_record.save()
            messages.error(request, f'WhisperX alignment 실패: {result["error"]}')
        
    except Exception as e:
        messages.error(request, f'처리 중 오류가 발생했습니다: {str(e)}')
        # 오류 발생 시 상태 초기화
        if 'audio_record' in locals():
            audio_record.alignment_status = 'failed'
            audio_record.save()
    
    return redirect('audio_detail', audio_id=audio_id)


@login_required
def get_alignment_data(request, audio_id):
    """
    저장된 alignment 데이터를 JSON으로 반환 (AJAX용)
    """
    try:
        audio_record = get_object_or_404(AudioRecord, id=audio_id)
        
        if not audio_record.alignment_data:
            return JsonResponse({
                'success': False,
                'error': 'No alignment data available'
            })
        
        # 프론트엔드용 포맷으로 변환
        formatted_data = format_alignment_for_frontend(audio_record.alignment_data)
        
        return JsonResponse({
            'success': True,
            'data': formatted_data,
            'status': audio_record.alignment_status
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def get_alignment_status(request, audio_id):
    """
    alignment 처리 상태를 확인하는 AJAX 엔드포인트
    """
    try:
        audio_record = get_object_or_404(AudioRecord, id=audio_id)
        
        return JsonResponse({
            'status': audio_record.alignment_status,
            'transcription_status': audio_record.status,
            'has_alignment_data': bool(audio_record.alignment_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        })


from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json

@method_decorator(csrf_exempt, name='dispatch')
class MobileUploadView(View):
    
    def post(self, request, category):
        """모바일 앱에서 오는 업로드 처리"""
        valid_categories = ['child', 'senior', 'atypical', 'auditory', 'normal']
        
        if category not in valid_categories:
            return JsonResponse({'error': 'Invalid category.'}, status=400)

        if not request.FILES.get('file'):
            return JsonResponse({'error': 'No file provided.'}, status=400)

        audio_file = request.FILES['file']
        
        try:
            # 공통 필드 데이터 추출
            common_data = {
                'audio_file': audio_file,
                'category': category,
                'identifier': request.POST.get('identifier'),
                'name': request.POST.get('name'),
                'gender': request.POST.get('gender'),
                'birth_year': request.POST.get('birthYear'),
                'birth_month': request.POST.get('birthMonth'),
                'birth_day': request.POST.get('birthDay'),
                'recording_location': request.POST.get('recordingLocation'),
                'noise_level': request.POST.get('noiseLevel'),
                'device_type': request.POST.get('deviceType'),
                'has_microphone': request.POST.get('hasMicrophone'),
                'diagnosis': request.POST.get('diagnosis'),
                'data_source': 'mobile_app'
            }
            
            # None 값 제거
            common_data = {k: v for k, v in common_data.items() if v is not None}
            
            # 레코드 생성
            audio_record = AudioRecord.objects.create(**common_data)
            
            # 카테고리별 특화 데이터 설정
            if category == 'child':
                audio_record.set_child_data(
                    place=request.POST.get('place'),
                    pronun_problem=request.POST.get('pronunProblem')
                )
            elif category == 'senior':
                audio_record.set_senior_data(
                    education=request.POST.get('education'),
                    has_voice_problem=request.POST.get('hasVoiceProblem')
                )
            elif category == 'auditory':
                audio_record.set_auditory_data(
                    education=request.POST.get('education'),
                    education_detail=request.POST.get('educationDetail'),
                    birth_date=request.POST.get('birthDate'),
                    recording_date=request.POST.get('recordingDate'),
                    hearing_onset_type=request.POST.get('hearingOnsetType'),
                    hearing_degree=request.POST.get('hearingDegree'),
                    hearing_level=request.POST.get('hearingLevel'),
                    hearing_loss_duration=request.POST.get('hearingLossDuration'),
                    has_hearing_aid=request.POST.get('hasHearingAid'),
                    hearing_aid_duration=request.POST.get('hearingAidDuration'),
                    cognitive_level=request.POST.get('cognitiveLevel'),
                    region=request.POST.get('region'),
                    has_voice_problem=request.POST.get('hasVoiceProblem'),
                    voice_problem_severity=request.POST.get('voiceProblemSeverity'),
                    voice_problem_note=request.POST.get('voiceProblemNote'),
                    attempts=request.POST.get('attempts')
                )
            
            audio_record.save()
            
            return JsonResponse({
                'message': 'File uploaded successfully.',
                'id': audio_record.id,
                'category': category,
                'common_fields': list(common_data.keys()),
                'category_specific_fields': list(audio_record.category_specific_data.keys())
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# 카테고리별 스키마 제공 API
class CategorySchemaView(View):
    def get(self, request, category):
        """카테고리별 필드 스키마 반환"""
        record = AudioRecord(category=category)
        schema = record.category_fields_schema
        
        return JsonResponse({
            'category': category,
            'schema': schema
        })

@require_http_methods(["POST"])
def update_category_data(request, audio_id):
    """카테고리별 특화 데이터 업데이트"""
    audio = get_object_or_404(AudioRecord, id=audio_id)
    
    try:
        # 카테고리별 필드 데이터 수집
        category_data = {}
        
        if audio.category == 'child':
            if request.POST.get('place'):
                category_data['place'] = request.POST.get('place')
            if request.POST.get('pronun_problem'):
                category_data['pronun_problem'] = request.POST.get('pronun_problem')
                
        elif audio.category == 'senior':
            if request.POST.get('education'):
                category_data['education'] = request.POST.get('education')
            if request.POST.get('has_voice_problem'):
                category_data['has_voice_problem'] = request.POST.get('has_voice_problem')
                
        elif audio.category == 'auditory':
            fields = [
                'education', 'education_detail', 'birth_date', 'recording_date',
                'hearing_onset_type', 'hearing_degree', 'hearing_level', 'hearing_loss_duration',
                'has_hearing_aid', 'hearing_aid_duration', 'cognitive_level', 'region',
                'has_voice_problem', 'voice_problem_severity', 'voice_problem_note', 'attempts'
            ]
            for field in fields:
                if request.POST.get(field):
                    category_data[field] = request.POST.get(field)
                    
        elif audio.category == 'atypical':
            fields = ['disorder_type', 'severity_level', 'therapy_history', 'medical_diagnosis']
            for field in fields:
                if request.POST.get(field):
                    category_data[field] = request.POST.get(field)
                    
        elif audio.category == 'normal':
            fields = ['education_level', 'occupation', 'dialect_region', 'recording_environment']
            for field in fields:
                if request.POST.get(field):
                    category_data[field] = request.POST.get(field)
        
        # 기존 카테고리 데이터와 병합
        if not audio.category_specific_data:
            audio.category_specific_data = {}
        
        audio.category_specific_data.update(category_data)
        audio.save()
        
        messages.success(request, f'✅ {audio.get_category_display()} 카테고리 정보가 성공적으로 업데이트되었습니다.')
        
    except Exception as e:
        messages.error(request, f'❌ 카테고리 정보 업데이트 실패: {str(e)}')
    
    return redirect('audio_detail', audio_id=audio_id)

def update_audio_metadata(request, audio_id):
    """기본 메타데이터 업데이트"""
    audio = get_object_or_404(AudioRecord, id=audio_id)
    
    if request.method == 'POST':
        try:
            # 기본 필드 업데이트
            fields_to_update = [
                'identifier', 'name', 'gender', 'birth_year', 'birth_month', 'birth_day',
                'category', 'recording_location', 'noise_level', 
                'device_type', 'has_microphone', 'diagnosis'
            ]
            
            # 성별 영어 → 한글 변환 매핑
            gender_mapping = {
                'male': '남',
                'female': '여',
                'Male': '남',
                'Female': '여',
                'MALE': '남',
                'FEMALE': '여',
                'M': '남',
                'F': '여',
                'm': '남',
                'f': '여'
            }
            
            for field in fields_to_update:
                value = request.POST.get(field)
                if value is not None:  # 빈 문자열도 허용
                    # 성별 필드인 경우 한글로 변환
                    if field == 'gender' and value:
                        value = gender_mapping.get(value, value)  # 매핑에 없으면 원본 유지
                    
                    setattr(audio, field, value if value else None)
            
            audio.save()
            messages.success(request, '✅ 메타데이터가 성공적으로 업데이트되었습니다.')
            
        except Exception as e:
            messages.error(request, f'❌ 메타데이터 업데이트 실패: {str(e)}')
    
    return redirect('audio_detail', audio_id=audio_id)

# API 뷰들
def alignment_status_api(request, audio_id):
    """Alignment 상태 확인 API"""
    try:
        audio = get_object_or_404(AudioRecord, id=audio_id)
        return JsonResponse({
            'status': audio.alignment_status,
            'has_data': bool(audio.alignment_data)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# React Native 파일 업로드 테스트 엔드포인트
@api_view(['POST'])
def test_file_upload(request):
    """React Native 앱의 파일 업로드 디버깅을 위한 테스트 엔드포인트"""
    try:
        print(f"[TEST] Test upload request from {request.META.get('REMOTE_ADDR')}")
        print(f"[TEST] Content-Type: {request.content_type}")
        print(f"[TEST] Request method: {request.method}")
        print(f"[TEST] Request encoding: {request.encoding}")
        
        # Request headers 확인
        relevant_headers = {}
        for header, value in request.META.items():
            if any(h in header.lower() for h in ['content', 'boundary', 'type', 'length']):
                relevant_headers[header] = value
        print(f"[TEST] Relevant headers: {relevant_headers}")
        
        # Files 확인
        print(f"[TEST] FILES keys: {list(request.FILES.keys())}")
        for key, file_obj in request.FILES.items():
            print(f"[TEST] File {key}: name={file_obj.name}, size={file_obj.size}, content_type={file_obj.content_type}")
        
        # Data 확인
        print(f"[TEST] DATA keys: {list(request.data.keys())}")
        for key, value in request.data.items():
            if key == 'file':
                print(f"[TEST] Data 'file' field: {type(value)} = {repr(value)}")
            else:
                print(f"[TEST] Data {key}: {type(value)} = {str(value)[:100]}")
        
        # POST 확인
        print(f"[TEST] POST keys: {list(request.POST.keys())}")
        
        # Raw body preview
        if hasattr(request, '_body') and request._body:
            body_preview = str(request._body[:1000])
            print(f"[TEST] Raw body preview: {body_preview}")
        
        # 성공적인 파일 업로드 여부 확인
        file = request.FILES.get('file')
        if file:
            return Response({
                'success': True,
                'message': '파일 업로드 성공!',
                'file_info': {
                    'name': file.name,
                    'size': file.size,
                    'content_type': file.content_type
                }
            }, status=200)
        else:
            return Response({
                'success': False,
                'message': '파일이 없습니다. React Native에서 FormData를 다음과 같이 수정해보세요:',
                'suggestions': [
                    '1. FormData에서 파일을 추가할 때: formData.append("file", { uri: recording.uri, type: "audio/wav", name: "recording.wav" });',
                    '2. 또는: formData.append("file", { uri: recording.uri, type: "audio/m4a", name: "recording.m4a" });',
                    '3. fetch 옵션에서: headers: { "Content-Type": "multipart/form-data" }를 제거하세요',
                    '4. React Native에서 파일 업로드 시 expo-document-picker나 react-native-image-picker 사용을 권장합니다'
                ],
                'debug_info': {
                    'content_type': request.content_type,
                    'files_keys': list(request.FILES.keys()),
                    'data_keys': list(request.data.keys()),
                    'has_boundary': 'boundary=' in (request.content_type or ''),
                    'encoding': request.encoding
                }
            }, status=400)
            
    except Exception as e:
        print(f"[TEST] Error in test endpoint: {str(e)}")
        return Response({
            'success': False,
            'error': f'서버 오류: {str(e)}'
        }, status=500)

def alignment_data_api(request, audio_id):
    """Alignment 데이터 반환 API"""
    try:
        audio = get_object_or_404(AudioRecord, id=audio_id)
        
        if not audio.alignment_data:
            return JsonResponse({
                'success': False,
                'error': 'Alignment 데이터가 없습니다.'
            })
        
        return JsonResponse({
            'success': True,
            'data': audio.alignment_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Assets 파일 목록 API
@csrf_exempt
@api_view(['GET'])
def api_assets_list(request):
    """
    Assets 폴더 구조 반환 (React Native용)
    예: /api/assets/list/
    """
    try:
        assets_root = settings.ASSETS_ROOT
        questions_path = os.path.join(assets_root, 'questions')
        
        structure = {}
        
        if os.path.exists(questions_path):
            for category in os.listdir(questions_path):
                category_path = os.path.join(questions_path, category)
                if os.path.isdir(category_path):
                    structure[category] = {}
                    for folder in os.listdir(category_path):
                        folder_path = os.path.join(category_path, folder)
                        if os.path.isdir(folder_path):
                            # 폴더 내 wav 파일 개수 세기
                            wav_files = [f for f in os.listdir(folder_path) if f.endswith('.wav')]
                            structure[category][folder] = {
                                'count': len(wav_files),
                                'url': f'/assets/questions/{category}/{folder}/'
                            }
        
        return Response({
            'success': True,
            'structure': structure,
            'base_url': settings.ASSETS_URL
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@api_view(['GET'])
def api_assets_files(request, category, folder):
    """
    특정 폴더의 wav 파일 목록 반환 (React Native용)
    예: /api/assets/list/auditory/jamo/
    """
    try:
        assets_root = settings.ASSETS_ROOT
        folder_path = os.path.join(assets_root, 'questions', category, folder)
        
        if not os.path.exists(folder_path):
            return Response({
                'success': False,
                'error': f'폴더를 찾을 수 없습니다: {category}/{folder}'
            }, status=404)
        
        files = []
        
        # 하위 디렉토리 처리 (sentence_easy는 List_1, List_2 등 하위 폴더가 있음)
        if os.path.isdir(folder_path):
            for item in sorted(os.listdir(folder_path)):
                item_path = os.path.join(folder_path, item)
                
                if os.path.isfile(item_path) and item.endswith('.wav'):
                    # 직접 wav 파일인 경우
                    files.append({
                        'filename': item,
                        'url': f'/assets/questions/{category}/{folder}/{item}',
                        'path': f'questions/{category}/{folder}/{item}'
                    })
                elif os.path.isdir(item_path):
                    # 하위 디렉토리가 있는 경우 (예: List_1, List_2)
                    for wav_file in sorted(os.listdir(item_path)):
                        if wav_file.endswith('.wav'):
                            files.append({
                                'filename': wav_file,
                                'subfolder': item,
                                'url': f'/assets/questions/{category}/{folder}/{item}/{wav_file}',
                                'path': f'questions/{category}/{folder}/{item}/{wav_file}'
                            })
        
        return Response({
            'success': True,
            'category': category,
            'folder': folder,
            'count': len(files),
            'files': files
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


def userprofile(request):
    """사용자 프로필 페이지 - 데이터 전송 위치 및 IP 접근 위치 시각화"""
    from django.db.models import Count
    from collections import defaultdict
    
    # === 데이터 전송 위치 통계 (category_specific_data의 region 기반) ===
    # 지역별 업로드 횟수 집계
    upload_locations = defaultdict(int)
    
    # region 필드가 있는 레코드들
    records_with_region = AudioRecord.objects.exclude(region__isnull=True).exclude(region__exact='')
    
    for record in records_with_region:
        region = record.region
        if region:
            upload_locations[region] += 1
    
    # 또는 category_specific_data에서 region 추출
    records_with_category_data = AudioRecord.objects.exclude(category_specific_data__isnull=True)
    
    for record in records_with_category_data:
        category_data = record.category_specific_data or {}
        region = category_data.get('region') or category_data.get('place')
        if region and region not in ['', 'null', None]:
            upload_locations[region] += 1
    
    # 지역 좌표 매핑 (한국 주요 지역)
    region_coordinates = {
        '서울': {'lat': 37.5665, 'lng': 126.9780},
        '경기': {'lat': 37.4138, 'lng': 127.5183},
        '인천': {'lat': 37.4563, 'lng': 126.7052},
        '강원': {'lat': 37.8228, 'lng': 128.1555},
        '충북': {'lat': 36.8, 'lng': 127.7},
        '충남': {'lat': 36.5184, 'lng': 126.8000},
        '대전': {'lat': 36.3504, 'lng': 127.3845},
        '전북': {'lat': 35.7175, 'lng': 127.153},
        '전남': {'lat': 34.8679, 'lng': 126.991},
        '광주': {'lat': 35.1595, 'lng': 126.8526},
        '경북': {'lat': 36.4919, 'lng': 128.8889},
        '경남': {'lat': 35.4606, 'lng': 128.2132},
        '대구': {'lat': 35.8714, 'lng': 128.6014},
        '울산': {'lat': 35.5384, 'lng': 129.3114},
        '부산': {'lat': 35.1796, 'lng': 129.0756},
        '제주': {'lat': 33.4996, 'lng': 126.5312},
        '가정': {'lat': 37.5665, 'lng': 126.9780},  # 기본값
        '병원': {'lat': 37.5665, 'lng': 126.9780},
        '센터': {'lat': 37.5665, 'lng': 126.9780},
        '어린이집': {'lat': 37.5665, 'lng': 126.9780},
    }
    
    # 업로드 위치 데이터 (지역 + 좌표 + 빈도수)
    upload_location_data = []
    for region, count in upload_locations.items():
        if region in region_coordinates:
            upload_location_data.append({
                'region': region,
                'count': count,
                'lat': region_coordinates[region]['lat'],
                'lng': region_coordinates[region]['lng']
            })
    
    # count 기준 내림차순 정렬
    upload_location_data.sort(key=lambda x: x['count'], reverse=True)
    
    # === IP 접근 위치 통계 (추후 구현을 위한 샘플 데이터) ===
    # 실제로는 Django의 request 로그나 별도 IP 추적 모델이 필요
    # 여기서는 샘플 데이터로 시연
    
    # TODO: 실제 IP 로그 수집 로직 구현
    # 예시: AccessLog 모델에서 IP 주소 추출 및 GeoIP로 좌표 변환
    
    # 샘플 IP 접근 위치 데이터 (이미 count 내림차순 정렬됨)
    ip_location_data = [
        {'city': '서울', 'count': 150, 'lat': 37.5665, 'lng': 126.9780},
        {'city': '부산', 'count': 45, 'lat': 35.1796, 'lng': 129.0756},
        {'city': '인천', 'count': 32, 'lat': 37.4563, 'lng': 126.7052},
        {'city': '대구', 'count': 28, 'lat': 35.8714, 'lng': 128.6014},
        {'city': '대전', 'count': 22, 'lat': 36.3504, 'lng': 127.3845},
        {'city': '광주', 'count': 18, 'lat': 35.1595, 'lng': 126.8526},
        {'city': '울산', 'count': 12, 'lat': 35.5384, 'lng': 129.3114},
        {'city': '제주', 'count': 8, 'lat': 33.4996, 'lng': 126.5312},
    ]
    
    context = {
        'upload_location_data': upload_location_data,
        'ip_location_data': ip_location_data,
        'total_uploads': sum([item['count'] for item in upload_location_data]),
        'total_access': sum([item['count'] for item in ip_location_data]),
    }
    
    return render(request, 'voice_app/userprofile.html', context)


@login_required
@require_http_methods(["POST"])
def audio_reupload(request, audio_id):
    """
    오디오 파일 재업로드 (보안 검증 포함)
    - 동일한 파일명만 허용
    - 실제 오디오 파일인지 검증
    - 원본 파일 백업
    - 변경 이력 기록
    """
    from .audio_reupload import replace_audio_file
    
    audio = get_object_or_404(AudioRecord, id=audio_id)
    
    # POST 요청만 허용
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'POST 요청만 허용됩니다'
        }, status=405)
    
    # 파일 확인
    if 'audio_file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': '파일이 업로드되지 않았습니다'
        }, status=400)
    
    new_file = request.FILES['audio_file']
    
    # 파일 교체 실행
    result = replace_audio_file(audio, new_file, request.user)
    
    if result['success']:
        messages.success(
            request,
            f'파일이 성공적으로 교체되었습니다. 백업: {os.path.basename(result["backup_path"])}'
        )
        return JsonResponse({
            'success': True,
            'message': '파일이 성공적으로 교체되었습니다',
            'backup_path': result['backup_path'],
            'old_hash': result['old_hash'],
            'new_hash': result['new_hash'],
            'validation': result['validation']
        })
    else:
        return JsonResponse({
            'success': False,
            'error': result['error'],
            'validation': result.get('validation', {})
        }, status=400)


@login_required
def audio_download(request, audio_id):
    """
    오디오 파일 다운로드
    """
    from django.http import FileResponse, Http404
    
    audio = get_object_or_404(AudioRecord, id=audio_id)
    
    if not audio.audio_file:
        raise Http404("오디오 파일이 존재하지 않습니다")
    
    if not os.path.exists(audio.audio_file.path):
        raise Http404("오디오 파일을 찾을 수 없습니다")
    
    # 원본 파일명 가져오기
    original_filename = os.path.basename(audio.audio_file.name)
    
    # 파일 응답
    response = FileResponse(
        open(audio.audio_file.path, 'rb'),
        as_attachment=True,
        filename=original_filename
    )
    
    return response


@login_required
def identifier_audio_list(request, identifier):
    """특정 고유 ID를 가진 모든 오디오 레코드를 테이블로 표시"""
    
    # 정렬 매개변수 처리
    sort_by = request.GET.get('sort', '-created_at')  # 기본값: 최신순
    valid_sort_fields = [
        'identifier', '-identifier',
        'id', '-id',
        'created_at', '-created_at',
        'name', '-name',
        'gender', '-gender',
        'age', '-age',
        'category', '-category',
        'status', '-status',
        'snr_mean', '-snr_mean',
        'snr_max', '-snr_max',
        'snr_min', '-snr_min',
        'region', '-region',
        'education_level', '-education_level',
        'hearing_level', '-hearing_level',
        'age_in_months', '-age_in_months'
    ]
    
    if sort_by not in valid_sort_fields:
        sort_by = '-created_at'
    
    # 해당 identifier를 가진 모든 오디오 레코드 조회
    audio_list_qs = AudioRecord.objects.filter(identifier=identifier).order_by(sort_by)
    
    # 각 오디오에 대해 React Native 메타데이터에서 기본 정보 추출
    for audio in audio_list_qs:
        extract_metadata_to_fields(audio)
    
    # 페이지네이션
    paginator = Paginator(audio_list_qs, 20)  # 한 페이지당 20개 항목
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 카테고리 통계 계산
    category_counts = {}
    for audio in audio_list_qs:
        category = audio.category
        category_counts[category] = category_counts.get(category, 0) + 1
    
    # 카테고리 이름 변환
    category_names = {
        'child': '아동',
        'senior': '노인', 
        'atypical': '음성 장애',
        'auditory': '청각 장애',
        'normal': '일반'
    }
    
    context = {
        'page_obj': page_obj,
        'audio_list': page_obj.object_list,
        'total_count': audio_list_qs.count(),
        'identifier': identifier,
        'category_counts': category_counts,
        'category_names': category_names,
        'current_sort': sort_by,
    }
    
    return render(request, 'voice_app/identifier_audio_list.html', context)
