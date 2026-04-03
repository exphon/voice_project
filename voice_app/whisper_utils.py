# voice_app/whisper_utils.py

import time
import os
import gc
import json
import re
import math
import tempfile
import subprocess
import wave
import audioop
import logging
import threading
import importlib.util
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

# whisperx는 선택적 의존성 (import 시점에 로딩/로그를 유발하지 않도록 스펙만 체크)
WHISPERX_AVAILABLE = importlib.util.find_spec("whisperx") is not None

# 💡 모델은 "전사할 때만" 1회 로딩 (lazy-load)
WHISPER_MODEL_NAME = "large-v3"
FORCED_LANGUAGE = "ko"
# NOTE: initial_prompt는 종종 출력으로 "유출"될 수 있어, 유출돼도 덜 어색하고
# 후처리로 제거하기 쉬운 짧은 지시문으로 유지합니다.
INITIAL_PROMPT_KO = "한국어로만 전사하세요. 음성에 없는 문장은 쓰지 마세요."

_WHISPER_MODEL = None
_WHISPER_MODEL_LOCK = threading.Lock()


def get_whisper_model():
    """Whisper 모델을 lazy loading으로 가져옴.

    - import 시점에 모델을 로딩하지 않음
    - 프로세스 내에서 최초 1회만 로딩
    """
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL

    with _WHISPER_MODEL_LOCK:
        if _WHISPER_MODEL is not None:
            return _WHISPER_MODEL
        try:
            import whisper  # heavy import
        except Exception:
            logger.exception("[Whisper] Failed to import whisper package")
            return None

        try:
            logger.info("[Whisper] Loading model (%s)...", WHISPER_MODEL_NAME)
            _WHISPER_MODEL = whisper.load_model(WHISPER_MODEL_NAME)
            logger.info("[Whisper] Model loaded (%s)", WHISPER_MODEL_NAME)
            return _WHISPER_MODEL
        except Exception:
            logger.exception("[Whisper] Failed to load model (%s)", WHISPER_MODEL_NAME)
            _WHISPER_MODEL = None
            return None


def _koreanize_common_english_tokens(text: str) -> str:
    """Best-effort normalization to keep outputs in Hangul when short English interjections appear.

    This does not attempt full translation; it only converts a small set of common tokens.
    """
    if not text:
        return text

    out = str(text)

    # Replace common short interjections (case-insensitive, whole-word)
    replacements = [
        # 음역(들리는 대로) 우선: 번역(meaning) 금지
        (re.compile(r"\bgood\b", re.IGNORECASE), "굿"),
        (re.compile(r"\bokay\b", re.IGNORECASE), "오케이"),
        (re.compile(r"\bok\b", re.IGNORECASE), "오케이"),
    ]
    for pattern, replacement in replacements:
        out = pattern.sub(replacement, out)

    return out


def _strip_non_korean_scripts(text: str) -> str:
    """Remove non-Korean scripts (e.g., Japanese Kana/Kanji, CJK ideographs) from transcripts.

    Goal: keep outputs Hangul-only (plus whitespace/punctuation) for UI/storage.

    - Strips characters in Japanese Hiragana/Katakana ranges and common CJK ideograph ranges.
    - Drops lines that end up with no Hangul at all.
    """
    if not text:
        return text

    # Hiragana/Katakana + halfwidth kana + CJK ideographs (incl. Extension A + compatibility)
    foreign_re = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\uff66-\uff9d\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
    hangul_re = re.compile(r"[\uac00-\ud7a3]")

    cleaned_lines: List[str] = []
    for raw_line in str(text).splitlines():
        line = foreign_re.sub("", raw_line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        # 한글이 전혀 없는 라인은 제거(외국어/기호-only 라인 제거 목적)
        if not hangul_re.search(line):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def _scrub_prompt_leakage(text: str) -> str:
    """Remove known prompt/instruction phrases when they leak into model outputs.

    Whisper/WhisperX는 initial_prompt 문구를 그대로 출력에 섞는 경우가 있습니다.
    실제 음성에 없는 '지시문'이 결과에 끼어들면 표시/API 단계에서 제거합니다.
    """
    if not text:
        return text

    def _normalize(s: str) -> str:
        s = (s or "").strip()
        s = re.sub(r"\s+", " ", s)
        # 흔한 구두점/대시만 제거 (의미 문장 훼손 최소화)
        s = s.strip(" \t\r\n\"'`“”‘’.,!?;:·…-–—")
        return s

    # 과거/현재 프롬프트 유출로 자주 보이는 문구들
    banned_exact = {
        _normalize("한국어 음성의 전사"),
        _normalize("다음은 한국어 음성의 전사입니다"),
        _normalize("다음은 한국어 음성의 전사입니다."),
        _normalize("가능한 한 정확히, 반드시 한국어로만 전사하세요"),
        _normalize("한국어로만 전사하세요"),
        _normalize("음성에 없는 문장은 쓰지 마세요"),
        _normalize("한국어 외 언어로 출력하지 마세요"),
        _normalize("외국어로 출력하지 마세요"),
        _normalize("일본어/영어/중국어 등 외국어로 출력하지 마세요"),
        _normalize(INITIAL_PROMPT_KO),
    }

    banned_substrings = [
        "한국어 음성의 전사",
        "다음은 한국어 음성의 전사",
        "한국어 외 언어로 출력하지 마세요",
        "외국어로 출력하지 마세요",
    ]

    # 라인 끝(또는 시작)에 붙는 지시문 변형 제거용
    instruction_tail_re = re.compile(
        r"\s*(?:"
        r"한국어\s*외\s*언어로\s*출력하지\s*마세요|"
        r"외국어로\s*출력하지\s*마세요|"
        r"일본어/영어/중국어\s*등\s*외국어로\s*출력하지\s*마세요|"
        r"한국어로만\s*전사하세요|"
        r"음성에\s*없는\s*문장은\s*쓰지\s*마세요|"
        r"가능한\s*한\s*정확히,\s*반드시\s*한국어로만\s*전사하세요|"
        r"다음은\s*한국어\s*음성의\s*전사입니다"
        r")\s*[\"'`“”‘’.,!?;:·…\-–—]*\s*$"
    )
    instruction_head_re = re.compile(
        r"^\s*(?:"
        r"한국어\s*외\s*언어로\s*출력하지\s*마세요|"
        r"외국어로\s*출력하지\s*마세요|"
        r"일본어/영어/중국어\s*등\s*외국어로\s*출력하지\s*마세요|"
        r"한국어로만\s*전사하세요|"
        r"음성에\s*없는\s*문장은\s*쓰지\s*마세요|"
        r"가능한\s*한\s*정확히,\s*반드시\s*한국어로만\s*전사하세요|"
        r"다음은\s*한국어\s*음성의\s*전사입니다"
        r")\s*[\"'`“”‘’.,!?;:·…\-–—]*\s*"
    )

    cleaned_lines: List[str] = []
    for raw_line in str(text).splitlines():
        line = raw_line

        # 라인 앞/뒤에 붙는 지시문 제거 (음성에 실제로 없을 확률이 매우 높음)
        line = instruction_head_re.sub("", line)
        line = instruction_tail_re.sub("", line)
        # 지시문 제거 후 남는 선행 구두점/공백 정리
        line = line.lstrip(" \t\r\n\"'`“”‘’.,!?;:·…-–—")

        # 라인 전체가 지시문이면 제거
        if _normalize(line) in banned_exact:
            continue

        # 라인 중간에 끼어든 대표 문구는 제거
        for sub in banned_substrings:
            if sub in line:
                line = line.replace(sub, "")

        # 제거 후 비면 drop
        if not _normalize(line):
            continue

        cleaned_lines.append(line.strip())

    out = "\n".join(cleaned_lines).strip()
    # 다중 공백 정리
    out = re.sub(r"\s{2,}", " ", out)
    return out

model = None

# WhisperX 모델 전역 변수 (lazy loading) - whisperx 사용 시에만 필요
whisperx_model = None
whisperx_model_a = None
whisperx_metadata = None
diarize_model = None

def get_whisperx_model():
    """WhisperX 모델을 lazy loading으로 가져옴"""
    global whisperx_model, whisperx_model_a, whisperx_metadata, diarize_model
    
    if not WHISPERX_AVAILABLE:
        logger.debug("[WhisperX] Not available (package not installed)")
        return None, None, None

    # heavy imports only when actually needed
    try:
        import torch
        import whisperx
    except Exception:
        logger.exception("[WhisperX] Failed to import whisperx/torch")
        return None, None, None
    
    if whisperx_model is None:
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            batch_size = 8 if device == "cuda" else 4  # batch size 줄임
            compute_type = "float16" if device == "cuda" else "int8"
            
            logger.info("[WhisperX] Loading model (large-v3) on %s...", device)
            # large-v3 모델 사용
            whisperx_model = whisperx.load_model("large-v3", device, compute_type=compute_type, language="ko")
            
            # alignment model (한국어 지원)
            whisperx_model_a, whisperx_metadata = whisperx.load_align_model(language_code="ko", device=device)
            
            logger.info("[WhisperX] Models loaded (large-v3)")
        except Exception as e:
            logger.exception("[WhisperX] Failed to load models")
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
    # Load model only when we really transcribe
    m = get_whisper_model()
    if not m:
        logger.error("[Whisper] Model not loaded")
        return None

    if not os.path.exists(audio_path):
        logger.error("[Whisper] File does not exist: %s", audio_path)
        return None

    def _looks_korean(text: str) -> bool:
        if not text:
            return False
        hangul_count = len(re.findall(r"[\uac00-\ud7a3]", text))
        # 공백/구두점 제외한 대략적인 글자수로 비율 계산
        core = re.sub(r"\s+", "", text)
        core = re.sub(r"[^0-9A-Za-z\uac00-\ud7a3]", "", core)
        if not core:
            return False
        return hangul_count > 0 and (hangul_count / max(len(core), 1)) >= 0.10

    def _contains_japanese(text: str) -> bool:
        if not text:
            return False
        # Hiragana/Katakana/CJK(한자 포함) 범위를 넓게 체크
        return bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text))

    try:
        start = time.time()

        try:
            import torch
            fp16 = torch.cuda.is_available()
        except Exception:
            fp16 = False

        options = {
            'fp16': fp16,
            'temperature': 0.0,
            'language': FORCED_LANGUAGE,
            'task': 'transcribe',
            'initial_prompt': INITIAL_PROMPT_KO,
            'beam_size': 5,
            'best_of': 5,
            'verbose': False,
        }

        try:
            result = m.transcribe(audio_path, **options)
        except TypeError as e:
            # whisper 버전에 따라 옵션이 미지원일 수 있어 안전하게 재시도
            msg = str(e)
            for key in ('task', 'initial_prompt', 'beam_size', 'best_of'):
                if key in options and f"'{key}'" in msg:
                    options.pop(key, None)
            result = m.transcribe(audio_path, **options)

        text = (result.get('text') or '').strip()

        # 결과가 한국어로 보이지 않으면(한글이 거의 없으면) 더 강한 프롬프트로 1회 재시도
        if text and not _looks_korean(text):
            retry_options = dict(options)
            retry_options['temperature'] = 0.0
            retry_options['language'] = FORCED_LANGUAGE
            retry_options['initial_prompt'] = INITIAL_PROMPT_KO + " 한국어 외 언어로 출력하지 마세요."
            try:
                result = m.transcribe(audio_path, **retry_options)
                text = (result.get('text') or '').strip()
            except Exception:
                # 재시도 실패 시 최초 결과 유지
                pass

        # 일본어/한자 등이 섞이고 한국어로 보이지 않으면 1회 추가 재시도
        if text and _contains_japanese(text) and not _looks_korean(text):
            retry2_options = dict(options)
            retry2_options['temperature'] = 0.0
            retry2_options['language'] = FORCED_LANGUAGE
            retry2_options['initial_prompt'] = (
                INITIAL_PROMPT_KO
                + " 일본어/영어/중국어 등 외국어로 출력하지 마세요. "
                + "반드시 한글로만 전사하세요."
            )
            try:
                result = m.transcribe(audio_path, **retry2_options)
                text = (result.get('text') or '').strip()
            except Exception:
                pass
        # 최종적으로 짧은 영어 토큰을 한글화
        text = _koreanize_common_english_tokens(text)
        text = _scrub_prompt_leakage(text)
        # 일본어/한자 등 비한글 스크립트 제거(한글-only 표시/저장)
        text = _strip_non_korean_scripts(text)

        elapsed = time.time() - start
        logger.info("[Whisper] Transcription completed in %.2f seconds", elapsed)
        return text
    except Exception as e:
        logger.exception("[Whisper] Failed to transcribe %s", audio_path)
        return None


def _ffmpeg_convert_to_wav_16k_mono(input_path: str) -> str:
    """Convert any audio file into a temporary 16kHz mono WAV (PCM 16-bit)."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.close()
    out_path = tmp.name
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        out_path,
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return out_path
    except Exception as e:
        try:
            os.unlink(out_path)
        except Exception:
            pass
        raise RuntimeError(f"ffmpeg convert failed: {e}")


def _extract_wav_segment(input_path: str, start_s: float, end_s: float) -> str:
    """Extract a time range to a temporary WAV (16kHz mono) for stable ASR."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.close()
    out_path = tmp.name
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ss", f"{start_s:.3f}",
        "-to", f"{end_s:.3f}",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        out_path,
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return out_path
    except Exception as e:
        try:
            os.unlink(out_path)
        except Exception:
            pass
        raise RuntimeError(f"ffmpeg segment extract failed: {e}")


def _merge_intervals(intervals: List[Tuple[float, float]], max_gap_s: float = 0.25) -> List[Tuple[float, float]]:
    if not intervals:
        return []
    intervals_sorted = sorted(intervals, key=lambda x: x[0])
    merged: List[Tuple[float, float]] = [intervals_sorted[0]]
    for start, end in intervals_sorted[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + max_gap_s:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _split_long_intervals(
    intervals: List[Tuple[float, float]],
    max_len_s: float = 20.0,
    overlap_s: float = 0.15,
) -> List[Tuple[float, float]]:
    if not intervals:
        return []
    out: List[Tuple[float, float]] = []
    for start, end in intervals:
        length = end - start
        if length <= max_len_s:
            out.append((start, end))
            continue
        t = start
        while t < end:
            chunk_end = min(t + max_len_s, end)
            out.append((t, chunk_end))
            if chunk_end >= end:
                break
            t = max(chunk_end - overlap_s, t + 0.01)
    return out


def vad_detect_speech_segments(
    audio_path: str,
    frame_ms: int = 30,
    threshold_dbfs: float = -35.0,
    min_speech_ms: int = 250,
    padding_ms: int = 200,
) -> List[Tuple[float, float]]:
    """Energy-based VAD (no extra deps): returns speech segments as (start_s, end_s).

    This improves mixed child/adult recordings by removing long silences and isolating short utterances.
    """
    wav_path = _ffmpeg_convert_to_wav_16k_mono(audio_path)
    try:
        with wave.open(wav_path, 'rb') as wf:
            sample_rate = wf.getframerate()
            sample_width = wf.getsampwidth()
            channels = wf.getnchannels()
            if sample_rate != 16000 or sample_width != 2 or channels != 1:
                raise RuntimeError("Unexpected WAV format after conversion")

            frame_size = int(sample_rate * (frame_ms / 1000.0))
            bytes_per_frame = frame_size * sample_width

            segments: List[Tuple[float, float]] = []
            in_speech = False
            speech_start = 0.0
            last_voiced_t = 0.0

            frame_index = 0
            while True:
                pcm = wf.readframes(frame_size)
                if not pcm:
                    break

                rms = audioop.rms(pcm, sample_width)
                # Convert RMS to dBFS-like value; clamp to avoid log(0)
                if rms <= 0:
                    dbfs = -120.0
                else:
                    dbfs = 20.0 * math.log10(rms / 32768.0)

                t = (frame_index * frame_size) / sample_rate
                voiced = dbfs >= threshold_dbfs

                if voiced:
                    last_voiced_t = t + (frame_ms / 1000.0)
                    if not in_speech:
                        in_speech = True
                        speech_start = max(0.0, t - (padding_ms / 1000.0))
                else:
                    if in_speech:
                        # if we've been non-voiced beyond padding, close segment
                        gap = t - last_voiced_t
                        if gap >= (padding_ms / 1000.0):
                            speech_end = min(last_voiced_t + (padding_ms / 1000.0), t)
                            if (speech_end - speech_start) * 1000.0 >= min_speech_ms:
                                segments.append((speech_start, speech_end))
                            in_speech = False

                frame_index += 1

            # flush tail
            if in_speech:
                speech_end = last_voiced_t + (padding_ms / 1000.0)
                if (speech_end - speech_start) * 1000.0 >= min_speech_ms:
                    segments.append((speech_start, speech_end))

        segments = _merge_intervals(segments, max_gap_s=0.25)
        return segments
    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass


def transcribe_audio_vad_segmented(
    audio_path: str,
    max_segment_s: float = 20.0,
    vad_threshold_dbfs: float = -35.0,
) -> Optional[str]:
    """VAD 기반으로 구간을 나눈 뒤 구간별 전사하여 합칩니다."""
    segments = vad_detect_speech_segments(audio_path, threshold_dbfs=vad_threshold_dbfs)
    if not segments:
        # fallback to whole-file transcription
        return transcribe_audio(audio_path)

    segments = _split_long_intervals(segments, max_len_s=max_segment_s, overlap_s=0.15)

    texts: List[str] = []
    for start_s, end_s in segments:
        # 너무 짧은 조각은 전사 노이즈가 많아서 skip
        if (end_s - start_s) < 0.20:
            continue
        seg_path = None
        try:
            seg_path = _extract_wav_segment(audio_path, start_s, end_s)
            seg_text = transcribe_audio(seg_path)
            if seg_text:
                texts.append(seg_text.strip())
        except Exception as e:
            print(f"[VAD] Segment transcribe failed ({start_s:.2f}-{end_s:.2f}s): {e}")
        finally:
            if seg_path:
                try:
                    os.unlink(seg_path)
                except Exception:
                    pass

    merged_text = " ".join([t for t in texts if t]).strip()
    return merged_text if merged_text else transcribe_audio(audio_path)


def transcribe_audio_with_diarization(
    audio_path: str,
    min_speakers: int = 1,
    max_speakers: int = 2,
    vad_threshold_dbfs: float = -35.0,
    max_segment_s: float = 20.0,
    include_speaker_labels: bool = False,
) -> Dict[str, Any]:
    """Pyannote diarization 후, 화자 라벨을 붙여 전사를 합칩니다.

    실패하거나 의존성이 없으면 VAD-only로 안전하게 폴백합니다.
    """
    try:
        from .diarization_utils import SpeakerDiarizer
    except Exception as e:
        text = transcribe_audio_vad_segmented(audio_path, max_segment_s=max_segment_s, vad_threshold_dbfs=vad_threshold_dbfs)
        return {
            'success': True,
            'mode': 'vad',
            'text': text or '',
            'diarization': None,
            'error': f"diarization unavailable: {e}",
        }

    diarizer = SpeakerDiarizer()
    diarization = diarizer.perform_diarization(
        audio_path,
        num_speakers=None,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )
    if diarization.get('status') != 'completed' or not diarization.get('segments'):
        text = transcribe_audio_vad_segmented(audio_path, max_segment_s=max_segment_s, vad_threshold_dbfs=vad_threshold_dbfs)
        return {
            'success': True,
            'mode': 'vad',
            'text': text or '',
            'diarization': diarization,
            'error': diarization.get('error'),
        }

    diarization = diarizer.assign_speaker_labels(diarization)

    # Merge adjacent same-speaker segments to reduce ffmpeg calls
    merged_segments: List[Dict[str, Any]] = []
    for seg in diarization['segments']:
        if not merged_segments:
            merged_segments.append(seg.copy())
            continue
        prev = merged_segments[-1]
        if seg['speaker'] == prev['speaker'] and seg['start'] <= prev['end'] + 0.25:
            prev['end'] = max(prev['end'], seg['end'])
            prev['duration'] = float(prev['end'] - prev['start'])
        else:
            merged_segments.append(seg.copy())

    lines: List[str] = []
    for seg in merged_segments:
        speaker = seg.get('speaker', '화자')
        start_s = float(seg.get('start', 0.0))
        end_s = float(seg.get('end', start_s))
        if end_s - start_s < 0.20:
            continue
        # segment를 또 VAD로 잘라서(짧은 단어/빠른 발화 대응) 전사 후 합치기
        seg_path = None
        try:
            seg_path = _extract_wav_segment(audio_path, start_s, end_s)
            seg_text = transcribe_audio_vad_segmented(seg_path, max_segment_s=max_segment_s, vad_threshold_dbfs=vad_threshold_dbfs)
            seg_text = (seg_text or '').strip()
            if seg_text:
                if include_speaker_labels:
                    lines.append(f"[{speaker}] {seg_text}")
                else:
                    lines.append(seg_text)
        except Exception as e:
            print(f"[Diarization] Segment transcribe failed ({speaker} {start_s:.2f}-{end_s:.2f}s): {e}")
        finally:
            if seg_path:
                try:
                    os.unlink(seg_path)
                except Exception:
                    pass

    text = "\n".join(lines).strip()
    if not text:
        text = transcribe_audio_vad_segmented(audio_path, max_segment_s=max_segment_s, vad_threshold_dbfs=vad_threshold_dbfs) or ''

    # diarization 결과가 한국어로 보이지 않으면(특히 일본어/한자 등) 전체 파일 단일 전사로 폴백
    # - 라벨을 제거한 텍스트 기준으로 판별하여 [아동] 같은 라벨이 판정을 방해하지 않게 함
    try:
        def _looks_korean_text(s: str) -> bool:
            if not s:
                return False
            hangul_count = len(re.findall(r"[\uac00-\ud7a3]", s))
            core = re.sub(r"\s+", "", s)
            core = re.sub(r"[^0-9A-Za-z\uac00-\ud7a3]", "", core)
            if not core:
                return False
            return hangul_count > 0 and (hangul_count / max(len(core), 1)) >= 0.10

        def _contains_japanese_text(s: str) -> bool:
            if not s:
                return False
            return bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", s))

        if text and (not _looks_korean_text(text)) and _contains_japanese_text(text):
            fallback = transcribe_audio(audio_path)
            if fallback and _looks_korean_text(fallback):
                text = fallback
    except Exception:
        # 판별/폴백 실패 시 diarization 결과 유지
        pass

    return {
        'success': True,
        'mode': 'diarization',
        'text': text,
        'diarization': diarization,
        'error': None,
    }


def transcribe_audio_mixed_child_adult(
    audio_path: str,
    prefer_diarization: bool = True,
    **kwargs,
) -> Dict[str, Any]:
    """5살 이하+성인 혼합 발화에 최적화된 전사.

    - diarization 가능하면 화자 라벨 포함 텍스트 반환
    - 실패/미설치 시 VAD-only로 폴백
    """
    if prefer_diarization:
        return transcribe_audio_with_diarization(audio_path, **kwargs)
    text = transcribe_audio_vad_segmented(audio_path, **kwargs)
    return {
        'success': True,
        'mode': 'vad',
        'text': text or '',
        'diarization': None,
        'error': None,
    }


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
    
    torch = None
    whisperx = None
    try:
        if not os.path.exists(audio_path):
            return {
                'transcription': '',
                'segments': [],
                'word_segments': [],
                'success': False,
                'error': f'File not found: {audio_path}'
            }
        
        # heavy imports only when actually needed
        import torch as _torch
        import whisperx as _whisperx
        torch = _torch
        whisperx = _whisperx

        device = "cuda" if torch.cuda.is_available() else "cpu"
        batch_size = 8 if device == "cuda" else 4  # batch size 줄임
        compute_type = "float16" if device == "cuda" else "int8"
        
        logger.info("[WhisperX] Starting transcription+alignment for: %s", audio_path)
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
        wx_options = {
            'batch_size': batch_size,
            'language': FORCED_LANGUAGE,
            'task': 'transcribe',
            'initial_prompt': INITIAL_PROMPT_KO,
        }
        try:
            result = whisperx_model.transcribe(audio, **wx_options)
        except TypeError as e:
            msg = str(e)
            for key in ('task', 'initial_prompt', 'language'):
                if key in wx_options and f"'{key}'" in msg:
                    wx_options.pop(key, None)
            result = whisperx_model.transcribe(audio, **wx_options)
        
        # 전사 텍스트 추출
        transcription = ""
        if 'segments' in result:
            transcription = " ".join([seg['text'] for seg in result['segments']])

        transcription = _koreanize_common_english_tokens(transcription)
        transcription = _scrub_prompt_leakage(transcription)
        transcription = _strip_non_korean_scripts(transcription)
        
        # 4. Forced alignment 수행
        result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
        
        # 5. 결과 정리
        segments = []
        word_segments = []
        
        if 'segments' in result:
            for segment in result['segments']:
                seg_text = segment.get('text', '')
                seg_text = _koreanize_common_english_tokens(seg_text)
                seg_text = _scrub_prompt_leakage(seg_text)
                seg_text = _strip_non_korean_scripts(seg_text)
                seg_data = {
                    'start': segment.get('start', 0),
                    'end': segment.get('end', 0),
                    'text': seg_text,
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
        logger.info("[WhisperX] Completed in %.2f seconds", elapsed)
        
        return {
            'transcription': transcription.strip(),
            'segments': segments,
            'word_segments': word_segments,
            'success': True,
            'error': None
        }
        
    except Exception as e:
        logger.exception("[WhisperX] Failed to process %s", audio_path)
        return {
            'transcription': '',
            'segments': [],
            'word_segments': [],
            'success': False,
            'error': str(e)
        }
    finally:
        # GPU 메모리 정리
        try:
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
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

