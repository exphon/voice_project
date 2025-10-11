"""
오디오 파일 재업로드 유틸리티
보안을 고려한 오디오 파일 교체 기능
"""

import os
import hashlib
import mimetypes
from django.core.files.uploadedfile import InMemoryUploadedFile
from pydub import AudioSegment
import io


def validate_audio_file(file):
    """
    업로드된 파일이 실제 오디오 파일인지 검증
    
    Args:
        file: Django UploadedFile 객체
        
    Returns:
        dict: {'valid': bool, 'error': str, 'format': str, 'duration': float}
    """
    result = {
        'valid': False,
        'error': '',
        'format': '',
        'duration': 0.0,
        'sample_rate': 0,
        'channels': 0
    }
    
    try:
        # 1. MIME 타입 확인
        content_type = file.content_type
        allowed_mime_types = [
            'audio/wav',
            'audio/wave',
            'audio/x-wav',
            'audio/mpeg',
            'audio/mp3',
            'audio/ogg',
            'audio/flac',
            'audio/x-flac',
            'audio/aac',
            'audio/m4a',
        ]
        
        if content_type not in allowed_mime_types:
            result['error'] = f'지원하지 않는 MIME 타입: {content_type}'
            return result
        
        # 2. 파일 확장자 확인
        file_name = file.name.lower()
        allowed_extensions = ['.wav', '.mp3', '.ogg', '.flac', '.aac', '.m4a']
        
        if not any(file_name.endswith(ext) for ext in allowed_extensions):
            result['error'] = f'지원하지 않는 파일 확장자: {file_name}'
            return result
        
        # 3. 파일 크기 확인 (최대 100MB)
        max_size = 100 * 1024 * 1024  # 100MB
        if file.size > max_size:
            result['error'] = f'파일 크기가 너무 큽니다 (최대 100MB, 현재: {file.size / 1024 / 1024:.2f}MB)'
            return result
        
        # 4. pydub으로 실제 오디오 파일인지 검증
        file.seek(0)
        file_bytes = file.read()
        file.seek(0)
        
        # 파일 포맷 추정
        if file_name.endswith('.wav'):
            audio_format = 'wav'
        elif file_name.endswith('.mp3'):
            audio_format = 'mp3'
        elif file_name.endswith('.ogg'):
            audio_format = 'ogg'
        elif file_name.endswith('.flac'):
            audio_format = 'flac'
        elif file_name.endswith('.m4a'):
            audio_format = 'm4a'
        elif file_name.endswith('.aac'):
            audio_format = 'aac'
        else:
            audio_format = 'wav'
        
        try:
            # AudioSegment로 로드 시도
            audio = AudioSegment.from_file(io.BytesIO(file_bytes), format=audio_format)
            
            # 오디오 속성 추출
            result['format'] = audio_format
            result['duration'] = len(audio) / 1000.0  # 초 단위
            result['sample_rate'] = audio.frame_rate
            result['channels'] = audio.channels
            
            # 최소 길이 확인 (0.1초 이상)
            if result['duration'] < 0.1:
                result['error'] = '오디오 파일이 너무 짧습니다 (최소 0.1초)'
                return result
            
            # 최대 길이 확인 (10분 이하)
            if result['duration'] > 600:
                result['error'] = '오디오 파일이 너무 깁니다 (최대 10분)'
                return result
            
            result['valid'] = True
            
        except Exception as audio_error:
            result['error'] = f'오디오 파일 분석 실패: {str(audio_error)}'
            return result
        
    except Exception as e:
        result['error'] = f'파일 검증 중 오류 발생: {str(e)}'
        return result
    
    return result


def verify_filename_match(original_filename, uploaded_filename):
    """
    원본 파일명과 업로드된 파일명이 일치하는지 확인
    
    Args:
        original_filename: 원본 파일명
        uploaded_filename: 업로드된 파일명
        
    Returns:
        bool: 일치 여부
    """
    # 파일명 정규화 (경로 제거, 소문자 변환)
    original_name = os.path.basename(original_filename).lower()
    uploaded_name = os.path.basename(uploaded_filename).lower()
    
    return original_name == uploaded_name


def calculate_file_hash(file):
    """
    파일의 SHA256 해시 계산
    
    Args:
        file: Django UploadedFile 객체
        
    Returns:
        str: 16진수 해시 문자열
    """
    sha256_hash = hashlib.sha256()
    
    file.seek(0)
    for byte_block in iter(lambda: file.read(4096), b""):
        sha256_hash.update(byte_block)
    file.seek(0)
    
    return sha256_hash.hexdigest()


def backup_original_file(audio_record):
    """
    원본 파일 백업
    
    Args:
        audio_record: AudioRecord 모델 인스턴스
        
    Returns:
        dict: {'success': bool, 'backup_path': str, 'error': str}
    """
    from django.conf import settings
    from datetime import datetime
    import shutil
    
    result = {
        'success': False,
        'backup_path': '',
        'error': ''
    }
    
    try:
        if not audio_record.audio_file:
            result['error'] = '원본 파일이 존재하지 않습니다'
            return result
        
        original_path = audio_record.audio_file.path
        
        if not os.path.exists(original_path):
            result['error'] = f'원본 파일을 찾을 수 없습니다: {original_path}'
            return result
        
        # 백업 디렉토리 생성
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'audio_backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # 백업 파일명 생성 (타임스탬프 포함)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_filename = os.path.basename(original_path)
        name, ext = os.path.splitext(original_filename)
        backup_filename = f"{name}_backup_{timestamp}{ext}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # 파일 복사
        shutil.copy2(original_path, backup_path)
        
        result['success'] = True
        result['backup_path'] = backup_path
        
    except Exception as e:
        result['error'] = f'백업 생성 실패: {str(e)}'
    
    return result


def replace_audio_file(audio_record, new_file, user):
    """
    오디오 파일 교체 (보안 검증 포함)
    
    Args:
        audio_record: AudioRecord 모델 인스턴스
        new_file: Django UploadedFile 객체
        user: 현재 사용자 (권한 확인용)
        
    Returns:
        dict: {
            'success': bool,
            'error': str,
            'backup_path': str,
            'old_hash': str,
            'new_hash': str,
            'validation': dict
        }
    """
    result = {
        'success': False,
        'error': '',
        'backup_path': '',
        'old_hash': '',
        'new_hash': '',
        'validation': {}
    }
    
    try:
        # 1. 권한 확인 (staff 또는 superuser만 허용)
        if not (user.is_staff or user.is_superuser):
            result['error'] = '파일 교체 권한이 없습니다'
            return result
        
        # 2. 파일명 일치 확인
        original_filename = os.path.basename(audio_record.audio_file.name)
        if not verify_filename_match(original_filename, new_file.name):
            result['error'] = f'파일명이 일치하지 않습니다 (원본: {original_filename}, 업로드: {new_file.name})'
            return result
        
        # 3. 오디오 파일 검증
        validation = validate_audio_file(new_file)
        result['validation'] = validation
        
        if not validation['valid']:
            result['error'] = validation['error']
            return result
        
        # 4. 원본 파일 해시 계산
        if audio_record.audio_file and os.path.exists(audio_record.audio_file.path):
            with open(audio_record.audio_file.path, 'rb') as f:
                old_file_content = f.read()
                result['old_hash'] = hashlib.sha256(old_file_content).hexdigest()
        
        # 5. 새 파일 해시 계산
        result['new_hash'] = calculate_file_hash(new_file)
        
        # 6. 원본 파일 백업
        backup_result = backup_original_file(audio_record)
        if not backup_result['success']:
            result['error'] = backup_result['error']
            return result
        
        result['backup_path'] = backup_result['backup_path']
        
        # 7. 파일 교체
        new_file.seek(0)
        audio_record.audio_file.save(
            os.path.basename(audio_record.audio_file.name),
            new_file,
            save=True
        )
        
        # 8. 메타데이터 업데이트 (duration 등)
        if validation.get('duration'):
            audio_record.duration = validation['duration']
        
        # 9. 변경 이력 기록 (category_specific_data에 추가)
        from datetime import datetime
        
        if not audio_record.category_specific_data:
            audio_record.category_specific_data = {}
        
        if 'file_history' not in audio_record.category_specific_data:
            audio_record.category_specific_data['file_history'] = []
        
        audio_record.category_specific_data['file_history'].append({
            'timestamp': datetime.now().isoformat(),
            'user': user.username,
            'action': 'replace',
            'old_hash': result['old_hash'],
            'new_hash': result['new_hash'],
            'backup_path': result['backup_path'],
            'validation': validation
        })
        
        audio_record.save()
        
        result['success'] = True
        
    except Exception as e:
        result['error'] = f'파일 교체 중 오류 발생: {str(e)}'
    
    return result
