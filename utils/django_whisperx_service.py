# Django에서 WhisperX를 사용하는 최적화된 서비스 클래스
# utils/whisperx_service.py

import os
import tempfile
import logging
from typing import Dict, List, Optional, Any
from django.conf import settings
import whisperx
import torch

logger = logging.getLogger(__name__)

class WhisperXService:
    """
    WhisperX를 Django에서 효율적으로 사용하기 위한 서비스 클래스
    """
    
    def __init__(self):
        self.config = getattr(settings, 'WHISPERX_CONFIG', {})
        self.model_size = self.config.get('MODEL_SIZE', 'base')
        self.device = self._get_best_device()
        self.compute_type = self.config.get('COMPUTE_TYPE', 'int8')
        
        # 모델 인스턴스들
        self._asr_model = None
        self._alignment_models = {}
        
        logger.info(f"WhisperX Service initialized with device: {self.device}")
    
    def _get_best_device(self) -> str:
        """최적의 디바이스 선택"""
        config_device = self.config.get('DEVICE', 'auto')
        
        if config_device == 'auto':
            if torch.cuda.is_available():
                # CUDA 사용 가능하지만 compute_type 호환성 확인
                try:
                    # 간단한 CUDA 테스트
                    test_tensor = torch.tensor([1.0]).cuda()
                    return 'cuda'
                except Exception as e:
                    logger.warning(f"CUDA available but test failed: {e}, falling back to CPU")
                    return 'cpu'
            else:
                return 'cpu'
        else:
            return config_device
    
    def _get_asr_model(self):
        """ASR 모델 로드 (싱글톤 패턴)"""
        if self._asr_model is None:
            try:
                self._asr_model = whisperx.load_model(
                    self.model_size, 
                    device=self.device,
                    compute_type=self.compute_type
                )
                logger.info(f"ASR model loaded: {self.model_size}")
            except Exception as e:
                logger.error(f"Failed to load ASR model: {e}")
                # CPU fallback
                if self.device == 'cuda':
                    logger.info("Falling back to CPU")
                    self.device = 'cpu'
                    self._asr_model = whisperx.load_model(
                        self.model_size, 
                        device='cpu',
                        compute_type='int8'
                    )
                else:
                    raise e
        return self._asr_model
    
    def _get_alignment_model(self, language_code: str):
        """언어별 정렬 모델 로드 (캐싱)"""
        if language_code not in self._alignment_models:
            try:
                alignment_model, metadata = whisperx.load_align_model(
                    language_code=language_code, 
                    device=self.device
                )
                self._alignment_models[language_code] = (alignment_model, metadata)
                logger.info(f"Alignment model loaded for language: {language_code}")
            except Exception as e:
                logger.error(f"Failed to load alignment model for {language_code}: {e}")
                raise e
        return self._alignment_models[language_code]
    
    def transcribe_audio(self, audio_path: str, **kwargs) -> Dict[str, Any]:
        """
        오디오 파일을 음성인식하고 정렬까지 수행
        
        Args:
            audio_path: 오디오 파일 경로
            **kwargs: 추가 옵션들
                - language: 언어 코드 (자동 감지 시 None)
                - batch_size: 배치 크기
                - temperature: 온도 설정
                - initial_prompt: 초기 프롬프트
        
        Returns:
            Dict with transcription results
        """
        try:
            # ASR 모델로 음성인식 수행
            model = self._get_asr_model()
            
            # 설정값들
            batch_size = kwargs.get('batch_size', self.config.get('BATCH_SIZE', 16))
            temperature = kwargs.get('temperature', self.config.get('TEMPERATURE', 0.0))
            initial_prompt = kwargs.get('initial_prompt', self.config.get('INITIAL_PROMPT'))
            language = kwargs.get('language', self.config.get('LANGUAGE'))
            
            # 음성인식 수행
            asr_options = {
                'batch_size': batch_size,
                'temperature': temperature,
            }
            if initial_prompt:
                asr_options['initial_prompt'] = initial_prompt
            if language:
                asr_options['language'] = language
                
            result = model.transcribe(audio_path, **asr_options)
            
            # 언어 감지 결과
            detected_language = result.get("language", "en")
            logger.info(f"Detected language: {detected_language}")
            
            # 정렬 수행 (단어 단위 타이밍)
            if self.config.get('WORD_TIMESTAMPS', True):
                try:
                    alignment_model, metadata = self._get_alignment_model(detected_language)
                    result = whisperx.align(
                        result["segments"], 
                        alignment_model, 
                        metadata, 
                        audio_path, 
                        device=self.device,
                        return_char_alignments=False
                    )
                    logger.info("Word-level alignment completed")
                except Exception as e:
                    logger.warning(f"Alignment failed, using ASR-only results: {e}")
            
            # 결과 가공
            segments = result.get("segments", [])
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
                    'compute_type': self.compute_type,
                    'batch_size': batch_size,
                    'temperature': temperature
                }
            }
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def get_supported_languages(self) -> List[str]:
        """지원되는 언어 목록 반환"""
        # WhisperX에서 지원하는 주요 언어들
        return [
            'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko',
            'ar', 'tr', 'pl', 'ca', 'nl', 'sv', 'no', 'da', 'fi', 'hu'
        ]
    
    def cleanup_models(self):
        """메모리 정리"""
        if self._asr_model is not None:
            del self._asr_model
            self._asr_model = None
        
        for lang, (model, metadata) in self._alignment_models.items():
            del model
            del metadata
        self._alignment_models.clear()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info("WhisperX models cleaned up")


# 전역 서비스 인스턴스
_whisperx_service = None

def get_whisperx_service() -> WhisperXService:
    """WhisperX 서비스 인스턴스 반환 (싱글톤)"""
    global _whisperx_service
    if _whisperx_service is None:
        _whisperx_service = WhisperXService()
    return _whisperx_service


# 편의 함수들
def transcribe_audio_file(audio_path: str, **kwargs) -> Dict[str, Any]:
    """오디오 파일 음성인식 편의 함수"""
    service = get_whisperx_service()
    return service.transcribe_audio(audio_path, **kwargs)

def cleanup_whisperx():
    """WhisperX 모델 메모리 정리"""
    global _whisperx_service
    if _whisperx_service is not None:
        _whisperx_service.cleanup_models()
        _whisperx_service = None
