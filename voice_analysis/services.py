import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

import librosa
import numpy as np
from scipy.signal import find_peaks, hilbert
from django.conf import settings
from django.db.models import Q
import parselmouth
from parselmouth.praat import call

from voice_app.models import AudioRecord

from .models import VoiceAnalysis


MAX_DISPLAY_POINTS = 4000
DEFAULT_PEAK_SENSITIVITY = 0.5
DEFAULT_MERGE_WINDOW_MS = 120
DEFAULT_VALLEY_RATIO = 0.58
DEFAULT_TRANSCRIPTION_TOKENS = ("퍼터커", "퍼", "터", "커")
DEFAULT_TRANSCRIPT_TOKEN = "퍼터커"

_HANGUL_BASE = 0xAC00
_HANGUL_LAST = 0xD7A3
_JUNGSUNG_EO_INDEX = 4
_CHOSUNG_STRIDE = 21 * 28
_JUNGSUNG_STRIDE = 28

_P_CLASS_CHOSEONG = {7, 8, 17}   # ㅂ, ㅃ, ㅍ
_T_CLASS_CHOSEONG = {3, 4, 16}   # ㄷ, ㄸ, ㅌ
_K_CLASS_CHOSEONG = {0, 1, 15}   # ㄱ, ㄲ, ㅋ


def _downsample_series(times, values, max_points=MAX_DISPLAY_POINTS):
    if len(times) <= max_points:
        return times, values

    sample_indexes = np.linspace(0, len(times) - 1, num=max_points, dtype=int)
    return times[sample_indexes], values[sample_indexes]


def _normalize_series(values):
    peak = float(np.max(np.abs(values))) if len(values) else 0.0
    if peak <= 0.0:
        return values
    return values / peak


def normalize_peak_sensitivity(value) -> float:
    try:
        sensitivity = float(value)
    except (TypeError, ValueError):
        sensitivity = DEFAULT_PEAK_SENSITIVITY

    return min(max(sensitivity, 0.05), 1.0)


def normalize_merge_window_ms(value) -> int:
    try:
        merge_window_ms = int(round(float(value)))
    except (TypeError, ValueError):
        merge_window_ms = DEFAULT_MERGE_WINDOW_MS
    return min(max(merge_window_ms, 40), 240)


def normalize_valley_ratio(value) -> float:
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        ratio = DEFAULT_VALLEY_RATIO
    return min(max(ratio, 0.30), 0.95)


def _peak_merge_parameters(peak_sensitivity: float, merge_window_ms=None, valley_ratio=None) -> tuple:
    if merge_window_ms is None:
        merge_window_seconds = 0.08 + (peak_sensitivity * 0.08)
    else:
        merge_window_seconds = normalize_merge_window_ms(merge_window_ms) / 1000.0

    if valley_ratio is None:
        valley_ratio = max(0.45, 0.7 - (peak_sensitivity * 0.25))
    else:
        valley_ratio = normalize_valley_ratio(valley_ratio)

    return merge_window_seconds, valley_ratio


def _merge_nearby_peaks(
    peak_indexes: np.ndarray,
    envelope_values: np.ndarray,
    sample_rate: int,
    peak_sensitivity: float,
    merge_window_ms=None,
    valley_ratio=None,
) -> np.ndarray:
    if peak_indexes.size <= 1:
        return peak_indexes

    merge_window_seconds, valley_ratio = _peak_merge_parameters(
        peak_sensitivity,
        merge_window_ms=merge_window_ms,
        valley_ratio=valley_ratio,
    )
    merged = [int(peak_indexes[0])]

    for current_peak in peak_indexes[1:]:
        current_peak = int(current_peak)
        previous_peak = int(merged[-1])

        peak_distance_seconds = (current_peak - previous_peak) / max(sample_rate, 1)
        if peak_distance_seconds > merge_window_seconds:
            merged.append(current_peak)
            continue

        start_index = min(previous_peak, current_peak)
        end_index = max(previous_peak, current_peak)
        valley_value = float(np.min(envelope_values[start_index : end_index + 1]))
        previous_peak_value = float(envelope_values[previous_peak])
        current_peak_value = float(envelope_values[current_peak])
        valley_threshold = valley_ratio * min(previous_peak_value, current_peak_value)

        if valley_value >= valley_threshold:
            if current_peak_value > previous_peak_value:
                merged[-1] = current_peak
        else:
            merged.append(current_peak)

    return np.array(merged, dtype=int)


def _save_preview_audio(temp_path: str, suffix: str) -> str:
    preview_dir = Path(settings.MEDIA_ROOT) / "voice_analysis_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    safe_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    file_name = f"{uuid.uuid4().hex}{safe_suffix.lower()}"
    output_path = preview_dir / file_name
    shutil.copyfile(temp_path, output_path)

    relative_path = f"voice_analysis_preview/{file_name}"
    return f"{settings.MEDIA_URL.rstrip('/')}/{relative_path}"


def summarize_repetition_tokens(text: str, tokens=DEFAULT_TRANSCRIPTION_TOKENS) -> dict:
    summary = {token: 0 for token in tokens}
    if not text:
        return summary

    for token in text.split():
        if token in summary:
            summary[token] += 1

    return summary


def _force_hangul_vowel_to_eo(char: str) -> str:
    code = ord(char)
    if code < _HANGUL_BASE or code > _HANGUL_LAST:
        return char

    syllable_index = code - _HANGUL_BASE
    choseong_index = syllable_index // _CHOSUNG_STRIDE
    jongseong_index = syllable_index % _JUNGSUNG_STRIDE
    forced_index = (
        choseong_index * _CHOSUNG_STRIDE
        + _JUNGSUNG_EO_INDEX * _JUNGSUNG_STRIDE
        + jongseong_index
    )
    return chr(_HANGUL_BASE + forced_index)


def _classify_consonant_token(char: str) -> str:
    code = ord(char)
    if code < _HANGUL_BASE or code > _HANGUL_LAST:
        return ""

    syllable_index = code - _HANGUL_BASE
    choseong_index = syllable_index // _CHOSUNG_STRIDE

    if choseong_index in _P_CLASS_CHOSEONG:
        return "퍼"
    if choseong_index in _T_CLASS_CHOSEONG:
        return "터"
    if choseong_index in _K_CLASS_CHOSEONG:
        return "커"
    return ""


def constrain_whisper_transcript(transcript_text: str) -> str:
    if not transcript_text:
        return ""

    forced_text = "".join(_force_hangul_vowel_to_eo(ch) for ch in transcript_text)
    classified_tokens = []
    for ch in forced_text:
        token = _classify_consonant_token(ch)
        if token:
            classified_tokens.append(token)

    if not classified_tokens:
        return ""

    constrained_tokens = []
    index = 0
    while index < len(classified_tokens):
        if (
            index + 2 < len(classified_tokens)
            and classified_tokens[index] == "퍼"
            and classified_tokens[index + 1] == "터"
            and classified_tokens[index + 2] == "커"
        ):
            constrained_tokens.append("퍼터커")
            index += 3
            continue

        constrained_tokens.append(classified_tokens[index])
        index += 1

    return " ".join(constrained_tokens)


def constrain_transcript_token_count(constrained_text: str, target_count: int) -> str:
    try:
        safe_target_count = max(int(target_count), 0)
    except (TypeError, ValueError):
        safe_target_count = 0

    if safe_target_count == 0:
        return ""

    tokens = [token for token in constrained_text.split() if token in DEFAULT_TRANSCRIPTION_TOKENS]
    if not tokens:
        tokens = [DEFAULT_TRANSCRIPT_TOKEN]

    if len(tokens) >= safe_target_count:
        return " ".join(tokens[:safe_target_count])

    expanded = []
    while len(expanded) < safe_target_count:
        expanded.append(tokens[len(expanded) % len(tokens)])

    return " ".join(expanded)


def resolve_preview_audio_path(audio_preview_url: str) -> str:
    if not audio_preview_url:
        return ""

    media_url = settings.MEDIA_URL.rstrip("/")
    normalized_url = audio_preview_url.strip()
    if normalized_url.startswith(media_url):
        relative_path = normalized_url[len(media_url):].lstrip("/")
    else:
        relative_path = normalized_url.lstrip("/")

    resolved_path = (Path(settings.MEDIA_ROOT) / relative_path).resolve()
    media_root = Path(settings.MEDIA_ROOT).resolve()

    if media_root not in resolved_path.parents and resolved_path != media_root:
        return ""

    if not resolved_path.exists() or not resolved_path.is_file():
        return ""

    return str(resolved_path)


def _match_audio_record_by_filename(uploaded_name: str):
    if not uploaded_name:
        return None

    base_name = Path(uploaded_name).name.strip()
    if not base_name:
        return None

    by_file_name = (
        AudioRecord.objects.filter(
            Q(audio_file__iendswith=f"/{base_name}") | Q(audio_file__iexact=base_name)
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if by_file_name:
        return by_file_name

    stem = Path(base_name).stem
    identifier_match = re.search(r"[CSA]\d{5}", stem, flags=re.IGNORECASE)
    if identifier_match:
        identifier = identifier_match.group(0).upper()
        return (
            AudioRecord.objects.filter(identifier=identifier)
            .order_by("-created_at", "-id")
            .first()
        )

    return None


def _build_speaker_info(audio_record: AudioRecord) -> dict:
    if not audio_record:
        return None

    birth_date = ""
    if audio_record.birth_year and audio_record.birth_month and audio_record.birth_day:
        birth_date = (
            f"{audio_record.birth_year}-"
            f"{str(audio_record.birth_month).zfill(2)}-"
            f"{str(audio_record.birth_day).zfill(2)}"
        )

    return {
        "name": audio_record.name or "",
        "identifier": audio_record.identifier or "",
        "category": audio_record.get_category_display() or "",
        "gender": audio_record.gender or "",
        "birth_date": birth_date,
        "age": audio_record.age or "",
        "region": audio_record.region or "",
        "recording_location": audio_record.recording_location or "",
        "diagnosis": audio_record.diagnosis or "",
    }


def analyze_waveform_only(uploaded_file) -> dict:
    """Analyzes waveform only, without envelope or transcription."""
    suffix = os.path.splitext(uploaded_file.name or "audio.wav")[1] or ".wav"
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)

        preview_audio_url = _save_preview_audio(temp_path, suffix)

        waveform, sample_rate = librosa.load(temp_path, sr=None, mono=True)
        if waveform.size == 0:
            raise ValueError("업로드한 오디오 파일에서 샘플을 읽지 못했습니다.")

        duration_seconds = float(len(waveform) / sample_rate)
        waveform_times = np.arange(len(waveform)) / sample_rate

        display_waveform_times, display_waveform = _downsample_series(waveform_times, waveform)
        normalized_waveform = _normalize_series(display_waveform)

        matched_audio_record = _match_audio_record_by_filename(uploaded_file.name)
        speaker_info = _build_speaker_info(matched_audio_record)

        return {
            "file_name": uploaded_file.name,
            "speaker_info": speaker_info,
            "audio_preview_url": preview_audio_url,
            "sample_rate": int(sample_rate),
            "duration_seconds": round(duration_seconds, 3),
            "waveform_points": [round(float(value), 6) for value in normalized_waveform.tolist()],
            "waveform_times": [round(float(value), 4) for value in display_waveform_times.tolist()],
            "zoom_enabled": duration_seconds > 10.0,
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def reanalyze_waveform_only(audio_preview_url: str) -> dict:
    audio_path = resolve_preview_audio_path(audio_preview_url)
    if not audio_path:
        raise ValueError("오디오 파일을 찾을 수 없습니다.")

    file_name = Path(audio_path).name
    with open(audio_path, "rb") as audio_stream:
        from django.core.files.uploadedfile import SimpleUploadedFile

        file_content = audio_stream.read()
        uploaded_file = SimpleUploadedFile(
            name=file_name,
            content=file_content,
            content_type="audio/wav",
        )

    result = analyze_waveform_only(uploaded_file)
    result["audio_preview_url"] = audio_preview_url
    return result


def analyze_sustained_vowel_segment(
    audio_preview_url: str,
    start_seconds,
    end_seconds,
) -> dict:
    audio_path = resolve_preview_audio_path(audio_preview_url)
    if not audio_path:
        raise ValueError("분석할 오디오 파일을 찾을 수 없습니다.")

    try:
        start_value = float(start_seconds)
        end_value = float(end_seconds)
    except (TypeError, ValueError):
        raise ValueError("선택 구간 정보가 올바르지 않습니다.")

    if end_value <= start_value:
        raise ValueError("선택 구간이 올바르지 않습니다.")

    sound = parselmouth.Sound(audio_path)
    total_duration = float(sound.get_total_duration())
    safe_start = min(max(start_value, 0.0), total_duration)
    safe_end = min(max(end_value, 0.0), total_duration)
    if safe_end <= safe_start:
        raise ValueError("선택 구간이 오디오 길이를 벗어났습니다.")

    segment_duration_seconds = safe_end - safe_start
    if segment_duration_seconds < 0.05:
        raise ValueError("분석 구간이 너무 짧습니다. 최소 50ms 이상 선택해 주세요.")

    segment = sound.extract_part(
        from_time=safe_start,
        to_time=safe_end,
        preserve_times=False,
    )

    midpoint = segment_duration_seconds / 2.0

    formant = call(segment, "To Formant (burg)", 0.0, 5, 5500.0, 0.025, 50.0)
    f1_value = call(formant, "Get value at time", 1, midpoint, "Hertz", "Linear")
    f2_value = call(formant, "Get value at time", 2, midpoint, "Hertz", "Linear")

    pitch = call(segment, "To Pitch", 0.0, 75.0, 500.0)
    point_process = call([segment, pitch], "To PointProcess (cc)")
    jitter_local = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
    shimmer_local = call([segment, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    harmonicity = call(segment, "To Harmonicity (cc)", 0.01, 75.0, 0.1, 1.0)
    hnr_value = call(harmonicity, "Get mean", 0, 0)

    power_cepstrogram = call(segment, "To PowerCepstrogram", 75.0, 0.005, 5000.0, 50.0)
    cpp_value = call(
        power_cepstrogram,
        "Get CPPS",
        True,
        0.02,
        0.0005,
        60.0,
        333.3,
        0.05,
        "parabolic",
        0.001,
        0.05,
        "Exponential decay",
        "Robust",
    )

    def _safe_number(value):
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if np.isnan(numeric) or np.isinf(numeric):
            return None
        return numeric

    return {
        "start_seconds": round(float(safe_start), 4),
        "end_seconds": round(float(safe_end), 4),
        "duration_ms": round(segment_duration_seconds * 1000.0, 2),
        "f1_hz": round(_safe_number(f1_value), 2) if _safe_number(f1_value) is not None else None,
        "f2_hz": round(_safe_number(f2_value), 2) if _safe_number(f2_value) is not None else None,
        "jitter_local": round(_safe_number(jitter_local), 6) if _safe_number(jitter_local) is not None else None,
        "shimmer_local": round(_safe_number(shimmer_local), 6) if _safe_number(shimmer_local) is not None else None,
        "hnr_db": round(_safe_number(hnr_value), 3) if _safe_number(hnr_value) is not None else None,
        "cpp": round(_safe_number(cpp_value), 3) if _safe_number(cpp_value) is not None else None,
    }


def analyze_waveform_envelope(
    uploaded_file,
    peak_sensitivity=DEFAULT_PEAK_SENSITIVITY,
    merge_window_ms=DEFAULT_MERGE_WINDOW_MS,
    valley_ratio=DEFAULT_VALLEY_RATIO,
    run_transcription=False,
    target_peak_count=None,
) -> dict:
    suffix = os.path.splitext(uploaded_file.name or "audio.wav")[1] or ".wav"
    temp_path = None
    peak_sensitivity = normalize_peak_sensitivity(peak_sensitivity)
    merge_window_ms = normalize_merge_window_ms(merge_window_ms)
    valley_ratio = normalize_valley_ratio(valley_ratio)

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)

        preview_audio_url = _save_preview_audio(temp_path, suffix)

        waveform, sample_rate = librosa.load(temp_path, sr=None, mono=True)
        if waveform.size == 0:
            raise ValueError("업로드한 오디오 파일에서 샘플을 읽지 못했습니다.")

        duration_seconds = float(len(waveform) / sample_rate)
        waveform_times = np.arange(len(waveform)) / sample_rate

        analytic_signal = hilbert(waveform)
        amplitude_envelope = np.abs(analytic_signal)
        smoothing_window = max(int(sample_rate * 0.01), 1)
        if smoothing_window > 1:
            kernel = np.ones(smoothing_window, dtype=np.float32) / smoothing_window
            amplitude_envelope = np.convolve(amplitude_envelope, kernel, mode="same")

        display_waveform_times, display_waveform = _downsample_series(waveform_times, waveform)
        display_envelope_times, display_envelope = _downsample_series(waveform_times, amplitude_envelope)

        normalized_waveform = _normalize_series(display_waveform)
        normalized_envelope = _normalize_series(display_envelope)
        envelope_peak = float(np.max(amplitude_envelope)) if amplitude_envelope.size else 0.0

        peak_height_ratio = max(0.08, 0.8 - (peak_sensitivity * 0.7))
        peak_height_threshold = float(envelope_peak * peak_height_ratio) if envelope_peak else 0.0
        peak_spacing_seconds = max(0.03, 0.22 - (peak_sensitivity * 0.16))
        min_peak_distance = max(int(sample_rate * peak_spacing_seconds), 1)
        peak_indexes, _ = find_peaks(
            amplitude_envelope,
            height=peak_height_threshold,
            distance=min_peak_distance,
        )
        peak_indexes = _merge_nearby_peaks(
            peak_indexes=peak_indexes,
            envelope_values=amplitude_envelope,
            sample_rate=sample_rate,
            peak_sensitivity=peak_sensitivity,
            merge_window_ms=merge_window_ms,
            valley_ratio=valley_ratio,
        )

        transcript_text = ""
        transcript_summary = {}
        if run_transcription:
            try:
                from voice_app.whisper_utils import transcribe_audio

                transcript_text = constrain_whisper_transcript((transcribe_audio(temp_path) or "").strip())
                if target_peak_count is not None:
                    transcript_text = constrain_transcript_token_count(transcript_text, target_peak_count)
                transcript_summary = summarize_repetition_tokens(transcript_text)
            except Exception:
                transcript_text = ""
                transcript_summary = {}

        matched_audio_record = _match_audio_record_by_filename(uploaded_file.name)
        speaker_info = _build_speaker_info(matched_audio_record)

        return {
            "file_name": uploaded_file.name,
            "speaker_info": speaker_info,
            "audio_preview_url": preview_audio_url,
            "sample_rate": int(sample_rate),
            "duration_seconds": round(duration_seconds, 3),
            "peak_sensitivity": round(float(peak_sensitivity), 2),
            "merge_window_ms": int(merge_window_ms),
            "valley_ratio": round(float(valley_ratio), 2),
            "peak_threshold_ratio": round(float(peak_height_ratio), 4),
            "transcription_enabled": bool(run_transcription),
            "transcript_text": transcript_text,
            "transcript_summary": transcript_summary,
            "target_peak_count": int(target_peak_count) if target_peak_count is not None else None,
            "waveform_points": [round(float(value), 6) for value in normalized_waveform.tolist()],
            "waveform_times": [round(float(value), 4) for value in display_waveform_times.tolist()],
            "envelope_points": [round(float(value), 6) for value in normalized_envelope.tolist()],
            "envelope_times": [round(float(value), 4) for value in display_envelope_times.tolist()],
            "peak_count": int(len(peak_indexes)),
            "zoom_enabled": duration_seconds > 10.0,
            "peak_points": [
                {
                    "time": round(float(index / sample_rate), 4),
                    "value": round(float(amplitude_envelope[index] / envelope_peak), 6) if envelope_peak else 0.0,
                }
                for index in peak_indexes.tolist()
            ],
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def reanalyze_saved_audio(
    audio_preview_url: str,
    peak_sensitivity=DEFAULT_PEAK_SENSITIVITY,
    merge_window_ms=DEFAULT_MERGE_WINDOW_MS,
    valley_ratio=DEFAULT_VALLEY_RATIO,
    run_transcription=True,
    target_peak_count=None,
) -> dict:
    audio_path = resolve_preview_audio_path(audio_preview_url)
    if not audio_path:
        raise ValueError("재전사할 오디오 파일을 찾을 수 없습니다.")

    file_name = Path(audio_path).name
    with open(audio_path, "rb") as audio_stream:
        from django.core.files.uploadedfile import SimpleUploadedFile

        file_content = audio_stream.read()
        uploaded_file = SimpleUploadedFile(
            name=file_name,
            content=file_content,
            content_type="audio/wav",
        )

    result = analyze_waveform_envelope(
        uploaded_file,
        peak_sensitivity=peak_sensitivity,
        merge_window_ms=merge_window_ms,
        valley_ratio=valley_ratio,
        run_transcription=run_transcription,
        target_peak_count=target_peak_count,
    )
    result["audio_preview_url"] = audio_preview_url
    return result


def build_basic_analysis_payload(audio_record: AudioRecord) -> dict:
    transcript_text = (audio_record.manual_transcript or audio_record.transcript or "").strip()
    transcript_lines = [line for line in transcript_text.splitlines() if line.strip()]

    return {
        "audio_record_id": audio_record.id,
        "identifier": audio_record.identifier,
        "category": audio_record.category,
        "status": audio_record.status,
        "alignment_status": audio_record.alignment_status,
        "diarization_status": audio_record.diarization_status,
        "num_speakers": audio_record.num_speakers,
        "has_manual_transcript": bool(audio_record.manual_transcript),
        "has_transcript": bool(audio_record.transcript),
        "transcript_line_count": len(transcript_lines),
        "transcript_character_count": len(transcript_text),
        "snr": {
            "mean": audio_record.snr_mean,
            "max": audio_record.snr_max,
            "min": audio_record.snr_min,
        },
        "metadata": {
            "gender": audio_record.gender,
            "age": audio_record.age,
            "region": audio_record.region,
            "recording_location": audio_record.recording_location,
            "device_type": audio_record.device_type,
            "noise_level": audio_record.noise_level,
        },
    }


def build_analysis_summary(result_data: dict) -> str:
    category = result_data.get("category") or "unknown"
    transcript_character_count = result_data.get("transcript_character_count") or 0
    num_speakers = result_data.get("num_speakers")
    speaker_text = f", speakers={num_speakers}" if num_speakers is not None else ""
    return f"category={category}, transcript_chars={transcript_character_count}{speaker_text}"


def analyze_audio_record(audio_record: AudioRecord, analysis_type: str = "basic", requested_by=None) -> VoiceAnalysis:
    analysis = VoiceAnalysis.objects.create(
        audio_record=audio_record,
        requested_by=requested_by,
        analysis_type=analysis_type,
        input_snapshot={
            "status": audio_record.status,
            "alignment_status": audio_record.alignment_status,
            "diarization_status": audio_record.diarization_status,
        },
    )

    analysis.mark_processing()
    analysis.save(update_fields=["status", "started_at", "updated_at"])

    try:
        if analysis_type == "basic":
            result_data = build_basic_analysis_payload(audio_record)
        else:
            result_data = {
                "audio_record_id": audio_record.id,
                "analysis_type": analysis_type,
                "message": "분석 로직이 아직 구현되지 않았습니다.",
            }

        analysis.mark_completed(
            result_data=result_data,
            summary=build_analysis_summary(result_data),
        )
    except Exception as exc:
        analysis.mark_failed(str(exc))

    analysis.save()
    return analysis