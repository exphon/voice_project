"""
Speaker Diarization Utilities using Pyannote
화자 분리(Speaker Diarization) 기능 구현
"""

import os
import torch
from pyannote.audio import Pipeline
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class SpeakerDiarizer:
    """
    Pyannote.audio를 사용한 화자 분리(Speaker Diarization) 클래스
    
    아동 음성 데이터에서 선생님과 아동의 발화를 자동으로 분리합니다.
    """
    
    def __init__(self, use_auth_token: Optional[str] = None):
        """
        Args:
            use_auth_token: Hugging Face 인증 토큰 (pyannote 모델 사용을 위해 필요)
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.pipeline = None
        self.use_auth_token = use_auth_token or os.environ.get('HUGGINGFACE_TOKEN')
        
        logger.info(f"🎙️ SpeakerDiarizer 초기화 (device: {self.device})")
    
    def load_pipeline(self):
        """Pyannote diarization 파이프라인 로드"""
        if self.pipeline is not None:
            return
        
        try:
            logger.info("📥 Pyannote diarization 파이프라인 로딩 중...")
            
            # Pyannote 3.x 버전 사용
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.use_auth_token
            )
            
            # GPU 사용 가능하면 GPU로 이동
            if torch.cuda.is_available():
                self.pipeline.to(self.device)
            
            logger.info("✅ Pyannote 파이프라인 로드 완료")
            
        except Exception as e:
            logger.error(f"❌ Pyannote 파이프라인 로드 실패: {e}")
            raise
    
    def perform_diarization(
        self, 
        audio_path: str, 
        num_speakers: Optional[int] = None,
        min_speakers: int = 1,
        max_speakers: int = 2
    ) -> Dict:
        """
        오디오 파일에 대해 화자 분리 수행
        
        Args:
            audio_path: 오디오 파일 경로
            num_speakers: 예상 화자 수 (None이면 자동 감지)
            min_speakers: 최소 화자 수
            max_speakers: 최대 화자 수
        
        Returns:
            Dict: {
                'segments': [{'start': float, 'end': float, 'speaker': str}, ...],
                'num_speakers': int,
                'status': str
            }
        """
        self.load_pipeline()
        
        try:
            logger.info(f"🎤 화자 분리 시작: {audio_path}")
            
            # Diarization 실행
            if num_speakers is not None:
                diarization = self.pipeline(
                    audio_path,
                    num_speakers=num_speakers
                )
            else:
                diarization = self.pipeline(
                    audio_path,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )
            
            # 결과를 JSON 직렬화 가능한 형태로 변환
            segments = []
            speakers = set()
            
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    'start': float(turn.start),
                    'end': float(turn.end),
                    'duration': float(turn.end - turn.start),
                    'speaker': speaker
                })
                speakers.add(speaker)
            
            # 화자별로 정렬 및 통계
            segments_sorted = sorted(segments, key=lambda x: x['start'])
            
            # 화자별 총 발화 시간 계산
            speaker_stats = {}
            for speaker in speakers:
                speaker_segments = [s for s in segments if s['speaker'] == speaker]
                total_duration = sum(s['duration'] for s in speaker_segments)
                speaker_stats[speaker] = {
                    'total_duration': total_duration,
                    'num_segments': len(speaker_segments),
                    'percentage': 0.0  # 나중에 계산
                }
            
            # 전체 발화 시간 대비 비율 계산
            total_speech_time = sum(s['duration'] for s in segments)
            for speaker in speaker_stats:
                speaker_stats[speaker]['percentage'] = (
                    speaker_stats[speaker]['total_duration'] / total_speech_time * 100
                    if total_speech_time > 0 else 0.0
                )
            
            result = {
                'segments': segments_sorted,
                'num_speakers': len(speakers),
                'speakers': list(speakers),
                'speaker_stats': speaker_stats,
                'total_speech_time': total_speech_time,
                'status': 'completed'
            }
            
            logger.info(f"✅ 화자 분리 완료: {len(speakers)}명의 화자 감지, {len(segments)}개 세그먼트")
            return result
            
        except Exception as e:
            logger.error(f"❌ 화자 분리 실패: {e}")
            return {
                'segments': [],
                'num_speakers': 0,
                'speakers': [],
                'speaker_stats': {},
                'total_speech_time': 0.0,
                'status': 'failed',
                'error': str(e)
            }
    
    def assign_speaker_labels(
        self,
        diarization_result: Dict,
        label_map: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        화자 레이블을 의미있는 이름으로 변경
        
        Args:
            diarization_result: perform_diarization 결과
            label_map: 화자 레이블 매핑 (예: {'SPEAKER_00': '아동', 'SPEAKER_01': '선생님'})
        
        Returns:
            레이블이 변경된 diarization 결과
        """
        if label_map is None:
            # 기본 매핑: 발화량이 많은 순서대로 아동, 선생님으로 추정
            speaker_stats = diarization_result.get('speaker_stats', {})
            sorted_speakers = sorted(
                speaker_stats.items(),
                key=lambda x: x[1]['total_duration'],
                reverse=True
            )
            
            label_map = {}
            labels = ['아동', '선생님', '화자3', '화자4']
            for idx, (speaker, _) in enumerate(sorted_speakers):
                if idx < len(labels):
                    label_map[speaker] = labels[idx]
                else:
                    label_map[speaker] = f'화자{idx + 1}'
        
        # 세그먼트의 화자 레이블 변경
        new_segments = []
        for segment in diarization_result['segments']:
            new_segment = segment.copy()
            original_speaker = segment['speaker']
            new_segment['speaker'] = label_map.get(original_speaker, original_speaker)
            new_segment['original_speaker'] = original_speaker
            new_segments.append(new_segment)
        
        # speaker_stats의 키도 변경
        new_speaker_stats = {}
        for original_speaker, stats in diarization_result['speaker_stats'].items():
            new_label = label_map.get(original_speaker, original_speaker)
            new_stats = stats.copy()
            new_stats['original_label'] = original_speaker
            new_speaker_stats[new_label] = new_stats
        
        # 새로운 화자 리스트
        new_speakers = [label_map.get(s, s) for s in diarization_result['speakers']]
        
        return {
            **diarization_result,
            'segments': new_segments,
            'speakers': new_speakers,
            'speaker_stats': new_speaker_stats,
            'label_map': label_map
        }
    
    def extract_speaker_audio(
        self,
        audio_path: str,
        diarization_result: Dict,
        speaker: str,
        output_path: str
    ) -> bool:
        """
        특정 화자의 발화만 추출하여 별도 파일로 저장
        
        Args:
            audio_path: 원본 오디오 파일 경로
            diarization_result: perform_diarization 결과
            speaker: 추출할 화자 레이블
            output_path: 출력 파일 경로
        
        Returns:
            성공 여부
        """
        try:
            from pydub import AudioSegment
            
            # 원본 오디오 로드
            audio = AudioSegment.from_wav(audio_path)
            
            # 해당 화자의 세그먼트만 추출
            speaker_segments = [
                s for s in diarization_result['segments']
                if s['speaker'] == speaker or s.get('original_speaker') == speaker
            ]
            
            if not speaker_segments:
                logger.warning(f"⚠️ 화자 '{speaker}'의 세그먼트를 찾을 수 없습니다.")
                return False
            
            # 세그먼트 병합
            combined_audio = AudioSegment.empty()
            for segment in speaker_segments:
                start_ms = int(segment['start'] * 1000)
                end_ms = int(segment['end'] * 1000)
                combined_audio += audio[start_ms:end_ms]
            
            # 파일 저장
            combined_audio.export(output_path, format="wav")
            logger.info(f"✅ 화자 '{speaker}' 오디오 추출 완료: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 화자 오디오 추출 실패: {e}")
            return False


def format_diarization_for_frontend(diarization_data: Dict) -> Dict:
    """
    Diarization 결과를 프론트엔드에서 표시하기 좋은 형태로 변환
    
    Args:
        diarization_data: perform_diarization 또는 assign_speaker_labels 결과
    
    Returns:
        프론트엔드용으로 포맷된 데이터
    """
    if not diarization_data or diarization_data.get('status') != 'completed':
        return {}
    
    # 시간 포맷팅 함수
    def format_time(seconds):
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:05.2f}"
    
    # 세그먼트를 화자별로 그룹화
    segments_by_speaker = {}
    for segment in diarization_data['segments']:
        speaker = segment['speaker']
        if speaker not in segments_by_speaker:
            segments_by_speaker[speaker] = []
        
        segments_by_speaker[speaker].append({
            'start': segment['start'],
            'end': segment['end'],
            'start_formatted': format_time(segment['start']),
            'end_formatted': format_time(segment['end']),
            'duration': segment['duration'],
            'duration_formatted': f"{segment['duration']:.2f}초"
        })
    
    # 타임라인 형태로도 제공 (WaveSurfer.js regions 등에 활용)
    timeline = []
    for segment in diarization_data['segments']:
        timeline.append({
            'start': segment['start'],
            'end': segment['end'],
            'speaker': segment['speaker'],
            'label': f"{segment['speaker']} ({format_time(segment['start'])} - {format_time(segment['end'])})"
        })
    
    return {
        'num_speakers': diarization_data['num_speakers'],
        'speakers': diarization_data['speakers'],
        'speaker_stats': diarization_data['speaker_stats'],
        'segments_by_speaker': segments_by_speaker,
        'timeline': timeline,
        'total_speech_time': diarization_data['total_speech_time'],
        'total_speech_time_formatted': format_time(diarization_data['total_speech_time'])
    }
