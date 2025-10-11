# voice_app/whisper_utils.py

import whisper
import time
import os
import gc
import torch
import json

# whisperx는 선택적 의존성
try:
    import whisperx
    WHISPERX_AVAILABLE = True
    print("[WhisperX] WhisperX module available")
except ImportError:
    WHISPERX_AVAILABLE = False
    print("[WhisperX] WhisperX module not available, using basic Whisper only")

# 💡 전역에서 한 번만 모델 로딩 (성능 최적화)
try:
    print("[Whisper] Loading model...")
    model = whisper.load_model("base")  # GPU 메모리 절약을 위해 base 모델 사용
    print("[Whisper] Model loaded successfully.")
except Exception as e:
    model = None
    print(f"[Whisper Error] Failed to load model: {e}")

# WhisperX 모델 전역 변수 (lazy loading) - whisperx 사용 시에만 필요
whisperx_model = None
whisperx_model_a = None
whisperx_metadata = None
diarize_model = None

def get_whisperx_model():
    """WhisperX 모델을 lazy loading으로 가져옴"""
    global whisperx_model, whisperx_model_a, whisperx_metadata, diarize_model
    
    if not WHISPERX_AVAILABLE:
        print("[WhisperX Error] WhisperX is not installed")
        return None, None, None
    
    if whisperx_model is None:
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            batch_size = 8 if device == "cuda" else 4  # batch size 줄임
            compute_type = "float16" if device == "cuda" else "int8"
            
            print(f"[WhisperX] Loading model on {device}...")
            # GPU 메모리 절약을 위해 base 또는 small 모델 사용
            whisperx_model = whisperx.load_model("base", device, compute_type=compute_type)
            
            # alignment model (한국어 지원)
            whisperx_model_a, whisperx_metadata = whisperx.load_align_model(language_code="ko", device=device)
            
            print("[WhisperX] Models loaded successfully.")
        except Exception as e:
            print(f"[WhisperX Error] Failed to load models: {e}")
            return None, None, None
    
    return whisperx_model, whisperx_model_a, whisperx_metadata


def transcribe_audio(audio_path):
    """
    오디오 파일 경로를 받아 Whisper로 전사하고 결과 텍스트를 반환.
    실패 시 None 반환.

    Args:
        audio_path (str): 파일 경로

    Returns:
        str or None: 전사 결과 또는 None
    """
    if not model:
        print("[Whisper Error] Model not loaded.")
        return None

    if not os.path.exists(audio_path):
        print(f"[Whisper Error] File does not exist: {audio_path}")
        return None

    try:
        start = time.time()
        result = model.transcribe(audio_path, fp16=False, temperature=0.0, language="ko")
        elapsed = time.time() - start
        print(f"[Whisper] Transcription completed in {elapsed:.2f} seconds.")
        return result['text']
    except Exception as e:
        print(f"[Whisper Error] Failed to transcribe {audio_path}: {e}")
        return None


def transcribe_and_align_whisperx(audio_path):
    """
    WhisperX를 사용하여 전사 및 forced alignment 수행
    
    Args:
        audio_path (str): 오디오 파일 경로
        
    Returns:
        dict: {
            'transcription': str,
            'segments': list,
            'word_segments': list,
            'success': bool,
            'error': str or None
        }
    """
    if not WHISPERX_AVAILABLE:
        return {
            'transcription': '',
            'segments': [],
            'word_segments': [],
            'success': False,
            'error': 'WhisperX is not installed. Please install it with: pip install whisperx'
        }
    
    try:
        if not os.path.exists(audio_path):
            return {
                'transcription': '',
                'segments': [],
                'word_segments': [],
                'success': False,
                'error': f'File not found: {audio_path}'
            }
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        batch_size = 8 if device == "cuda" else 4  # batch size 줄임
        compute_type = "float16" if device == "cuda" else "int8"
        
        print(f"[WhisperX] Starting transcription and alignment for: {audio_path}")
        start_time = time.time()
        
        # 1. 오디오 로드
        audio = whisperx.load_audio(audio_path)
        
        # 2. WhisperX 모델 로드
        whisperx_model, model_a, metadata = get_whisperx_model()
        if whisperx_model is None:
            return {
                'transcription': '',
                'segments': [],
                'word_segments': [],
                'success': False,
                'error': 'Failed to load WhisperX models'
            }
        
        # 3. 전사 수행 (한국어로 고정)
        result = whisperx_model.transcribe(audio, batch_size=batch_size, language="ko")
        
        # 전사 텍스트 추출
        transcription = ""
        if 'segments' in result:
            transcription = " ".join([seg['text'] for seg in result['segments']])
        
        # 4. Forced alignment 수행
        result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
        
        # 5. 결과 정리
        segments = []
        word_segments = []
        
        if 'segments' in result:
            for segment in result['segments']:
                seg_data = {
                    'start': segment.get('start', 0),
                    'end': segment.get('end', 0),
                    'text': segment.get('text', ''),
                    'id': segment.get('id', 0)
                }
                segments.append(seg_data)
                
                # 단어 레벨 alignment
                if 'words' in segment:
                    for word in segment['words']:
                        word_data = {
                            'start': word.get('start', 0),
                            'end': word.get('end', 0),
                            'word': word.get('word', ''),
                            'score': word.get('score', 0.0),
                            'segment_id': segment.get('id', 0)
                        }
                        word_segments.append(word_data)
        
        elapsed = time.time() - start_time
        print(f"[WhisperX] Completed in {elapsed:.2f} seconds")
        
        return {
            'transcription': transcription.strip(),
            'segments': segments,
            'word_segments': word_segments,
            'success': True,
            'error': None
        }
        
    except Exception as e:
        print(f"[WhisperX Error] Failed to process {audio_path}: {e}")
        return {
            'transcription': '',
            'segments': [],
            'word_segments': [],
            'success': False,
            'error': str(e)
        }
    finally:
        # GPU 메모리 정리
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()


def format_alignment_for_frontend(alignment_data):
    """
    alignment 데이터를 프론트엔드에서 사용하기 쉬운 형태로 변환
    
    Args:
        alignment_data (dict): WhisperX alignment 결과
        
    Returns:
        dict: 프론트엔드용 포맷된 데이터
    """
    if not alignment_data or not alignment_data.get('success'):
        return {
            'segments': [],
            'words': [],
            'transcription': '',
            'duration': 0
        }
    
    segments = alignment_data.get('segments', [])
    words = alignment_data.get('word_segments', [])
    
    # 전체 길이 계산
    duration = 0
    if segments:
        duration = max([seg.get('end', 0) for seg in segments])
    elif words:
        duration = max([word.get('end', 0) for word in words])
    
    return {
        'segments': segments,
        'words': words,
        'transcription': alignment_data.get('transcription', ''),
        'duration': duration
    }

