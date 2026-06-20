import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
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
DEFAULT_PEAK_SENSITIVITY = 0.8
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


# disvoice Phonation feature labels mapped to friendly keys for the template.
# The static extractor returns 28 values (avg/std/skewness/kurtosis × 7 measures);
# we surface the avg/std subset that is most interpretable for sustained vowels.
_DISVOICE_PHONATION_FIELDS = [
    ("avg DF0", "avg_df0"),
    ("avg DDF0", "avg_ddf0"),
    ("avg Jitter", "avg_jitter"),
    ("avg Shimmer", "avg_shimmer"),
    ("avg apq", "avg_apq"),
    ("avg ppq", "avg_ppq"),
    ("avg logE", "avg_log_energy"),
    ("std DF0", "std_df0"),
    ("std DDF0", "std_ddf0"),
    ("std Jitter", "std_jitter"),
    ("std Shimmer", "std_shimmer"),
    ("std apq", "std_apq"),
    ("std ppq", "std_ppq"),
    ("std logE", "std_log_energy"),
]


def _compute_disvoice_phonation(segment) -> dict:
    """Run disvoice's Phonation static feature extraction on a parselmouth segment.

    The segment is saved to a temporary WAV file because disvoice reads from disk.
    Returns a dict keyed by friendly names, or {} if extraction is unavailable.
    The heavy import is done lazily so module import stays fast.
    """
    try:
        from disvoice.phonation import Phonation
    except Exception:
        return {}

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_path = temp_file.name
        segment.save(temp_path, "WAV")

        phonation = Phonation()
        features = phonation.extract_features_file(
            temp_path, static=True, plots=False, fmt="dataframe"
        )
        if features is None or features.empty:
            return {}

        row = features.to_dict("records")[0]
        result = {}
        for source_key, friendly_key in _DISVOICE_PHONATION_FIELDS:
            value = _safe_number(row.get(source_key))
            result[friendly_key] = round(value, 6) if value is not None else None
        return result
    except Exception:
        return {}
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


# disvoice Glottal feature labels mapped to friendly keys for the template.
# The static extractor returns 36 values (avg/std/skewness/kurtosis × 9 measures);
# we surface the "global avg" subset (the mean across glottal cycles) which is the
# most interpretable view of glottal source behaviour for a sustained vowel.
_DISVOICE_GLOTTAL_FIELDS = [
    ("global avg var GCI", "var_gci"),
    ("global avg avg NAQ", "avg_naq"),
    ("global avg std NAQ", "std_naq"),
    ("global avg avg QOQ", "avg_qoq"),
    ("global avg std QOQ", "std_qoq"),
    ("global avg avg H1H2", "avg_h1h2"),
    ("global avg std H1H2", "std_h1h2"),
    ("global avg avg HRF", "avg_hrf"),
    ("global avg std HRF", "std_hrf"),
]


def _compute_disvoice_glottal(segment) -> dict:
    """Run disvoice's Glottal static feature extraction on a parselmouth segment.

    The segment is saved to a temporary WAV file because disvoice reads from disk.
    Returns a dict keyed by friendly names, or {} if extraction is unavailable.
    The heavy import is done lazily so module import stays fast.
    """
    try:
        from disvoice.glottal import Glottal
    except Exception:
        return {}

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_path = temp_file.name
        segment.save(temp_path, "WAV")

        glottal = Glottal()
        features = glottal.extract_features_file(
            temp_path, static=True, plots=False, fmt="dataframe"
        )
        if features is None or features.empty:
            return {}

        row = features.to_dict("records")[0]
        result = {}
        for source_key, friendly_key in _DISVOICE_GLOTTAL_FIELDS:
            value = _safe_number(row.get(source_key))
            result[friendly_key] = round(value, 6) if value is not None else None
        return result
    except Exception:
        return {}
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _compute_cepstral_profile(samples: np.ndarray, sample_rate: int) -> dict:
    if sample_rate <= 0 or samples.size == 0:
        return {}

    centered = samples.astype(np.float64, copy=False)
    centered = centered - np.mean(centered)
    if not np.any(centered):
        return {}

    windowed = centered * np.hanning(len(centered))
    fft_size = max(2048, int(2 ** np.ceil(np.log2(max(len(windowed), 1)))))
    spectrum = np.fft.rfft(windowed, n=fft_size)
    log_spectrum = np.log(np.abs(spectrum) + 1e-12)
    cepstrum = np.fft.irfft(log_spectrum, n=fft_size)

    quefrency_seconds = np.arange(len(cepstrum), dtype=np.float64) / float(sample_rate)
    quefrency_ms = quefrency_seconds * 1000.0

    min_quefrency_ms = 1.0
    max_quefrency_ms = 20.0
    valid_mask = (quefrency_ms >= min_quefrency_ms) & (quefrency_ms <= max_quefrency_ms)
    valid_indexes = np.flatnonzero(valid_mask)
    if valid_indexes.size < 3:
        return {}

    cepstrum_db = 20.0 * np.log10(np.abs(cepstrum) + 1e-12)
    valid_quefrency_ms = quefrency_ms[valid_indexes]
    valid_magnitude_db = cepstrum_db[valid_indexes]

    regression = np.polyfit(valid_quefrency_ms, valid_magnitude_db, 1)
    regression_values = np.polyval(regression, valid_quefrency_ms)

    peak_offset = int(np.argmax(valid_magnitude_db))
    peak_index = int(valid_indexes[peak_offset])
    peak_quefrency_ms = float(quefrency_ms[peak_index])
    peak_magnitude_db = float(cepstrum_db[peak_index])
    regression_at_peak = float(np.polyval(regression, peak_quefrency_ms))
    cpp_prominence_db = peak_magnitude_db - regression_at_peak
    peak_frequency_hz = 1000.0 / peak_quefrency_ms if peak_quefrency_ms > 0 else None

    return {
        "quefrency_ms": [round(float(value), 4) for value in valid_quefrency_ms.tolist()],
        "magnitude_db": [round(float(value), 4) for value in valid_magnitude_db.tolist()],
        "regression_db": [round(float(value), 4) for value in regression_values.tolist()],
        "regression_slope": round(float(regression[0]), 6),
        "regression_intercept": round(float(regression[1]), 4),
        "peak_quefrency_ms": round(peak_quefrency_ms, 4),
        "peak_period_ms": round(peak_quefrency_ms, 4),
        "peak_frequency_hz": round(float(peak_frequency_hz), 4) if peak_frequency_hz is not None else None,
        "peak_magnitude_db": round(peak_magnitude_db, 4),
        "regression_at_peak_db": round(regression_at_peak, 4),
        "cpp_prominence_db": round(float(cpp_prominence_db), 4),
    }


def _detect_vowel_boundaries(waveform: np.ndarray, sample_rate: int) -> tuple:
    """Returns (onset_seconds, offset_seconds) using RMS energy thresholding."""
    hop_length = max(int(sample_rate * 0.01), 1)
    frame_length = max(int(sample_rate * 0.025), 2)
    rms = librosa.feature.rms(y=waveform, frame_length=frame_length, hop_length=hop_length)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sample_rate, hop_length=hop_length)
    peak_rms = float(np.max(rms)) if rms.size else 0.0
    if peak_rms == 0.0:
        return 0.0, float(len(waveform) / max(sample_rate, 1))
    above = rms > peak_rms * 0.08
    if not np.any(above):
        return 0.0, float(len(waveform) / max(sample_rate, 1))
    onset_idx = int(np.argmax(above))
    offset_idx = int(len(above) - 1 - int(np.argmax(above[::-1])))
    return float(rms_times[onset_idx]), float(rms_times[offset_idx])


def _compute_spectrogram(waveform: np.ndarray, sample_rate: int, max_freq: float = 8000.0) -> dict:
    """Returns a downsampled normalized spectrogram dict for visualization."""
    n_fft = 1024
    hop_length = max(int(sample_rate * 0.008), 1)
    stft = np.abs(librosa.stft(waveform, n_fft=n_fft, hop_length=hop_length))
    spec_db = librosa.amplitude_to_db(stft, ref=np.max)
    freqs_all = librosa.fft_frequencies(sr=sample_rate, n_fft=n_fft)
    freq_mask = freqs_all <= max_freq
    spec_db_lim = spec_db[freq_mask, :]
    freqs_lim = freqs_all[freq_mask]
    max_t, max_f = 250, 100
    t_step = max(1, spec_db_lim.shape[1] // max_t)
    f_step = max(1, spec_db_lim.shape[0] // max_f)
    spec_ds = spec_db_lim[::f_step, ::t_step]
    freqs_ds = freqs_lim[::f_step]
    times_ds = librosa.frames_to_time(
        np.arange(0, spec_db_lim.shape[1], t_step), sr=sample_rate, hop_length=hop_length,
    )
    spec_min = float(np.min(spec_ds))
    spec_max = float(np.max(spec_ds))
    spec_range = spec_max - spec_min if spec_max > spec_min else 1.0
    spec_norm = (spec_ds - spec_min) / spec_range
    return {
        "data": [[round(float(v), 3) for v in row] for row in spec_norm.tolist()],
        "times": [round(float(t), 4) for t in times_ds.tolist()],
        "freqs": [round(float(f), 1) for f in freqs_ds.tolist()],
    }


def analyze_waveform_only(uploaded_file, include_spectrogram: bool = False) -> dict:
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

        vowel_onset, vowel_offset = _detect_vowel_boundaries(waveform, sample_rate)

        result = {
            "file_name": uploaded_file.name,
            "speaker_info": speaker_info,
            "audio_record_id": matched_audio_record.id if matched_audio_record else None,
            "audio_preview_url": preview_audio_url,
            "sample_rate": int(sample_rate),
            "duration_seconds": round(duration_seconds, 3),
            "waveform_points": [round(float(value), 6) for value in normalized_waveform.tolist()],
            "waveform_times": [round(float(value), 4) for value in display_waveform_times.tolist()],
            "zoom_enabled": duration_seconds > 10.0,
            "vowel_onset": round(vowel_onset, 4),
            "vowel_offset": round(vowel_offset, 4),
        }
        if include_spectrogram:
            result["spectrogram"] = _compute_spectrogram(waveform, sample_rate)
        return result
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def reanalyze_waveform_only(audio_preview_url: str, include_spectrogram: bool = False) -> dict:
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

    result = analyze_waveform_only(uploaded_file, include_spectrogram=include_spectrogram)
    result["audio_preview_url"] = audio_preview_url
    return result


def _load_saved_vowel_markers(audio_record_id):
    """Return {onset, offset} from the latest saved vowel_marker VoiceAnalysis, or None."""
    if not audio_record_id:
        return None
    from .models import VoiceAnalysis
    record = (
        VoiceAnalysis.objects
        .filter(audio_record_id=int(audio_record_id), analysis_type="vowel_marker", status="completed")
        .order_by("-updated_at")
        .first()
    )
    if not record:
        return None
    onset  = record.result_data.get("onset")
    offset = record.result_data.get("offset")
    if onset is not None and offset is not None:
        return {"onset": float(onset), "offset": float(offset)}
    return None


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
    segment_samples = np.asarray(segment.values[0], dtype=np.float64)
    cepstral_profile = _compute_cepstral_profile(segment_samples, int(segment.sampling_frequency))
    disvoice_phonation = _compute_disvoice_phonation(segment)
    disvoice_glottal = _compute_disvoice_glottal(segment)

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
        "cepstrum_profile": cepstral_profile,
        "disvoice_phonation": disvoice_phonation,
        "disvoice_glottal": disvoice_glottal,
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


def analyze_waveform_envelope_from_url(
    audio_preview_url: str,
    peak_sensitivity=DEFAULT_PEAK_SENSITIVITY,
    merge_window_ms=DEFAULT_MERGE_WINDOW_MS,
    valley_ratio=DEFAULT_VALLEY_RATIO,
    run_transcription=False,
    target_peak_count=None,
) -> dict:
    audio_path = resolve_preview_audio_path(audio_preview_url)
    if not audio_path:
        raise ValueError("분석할 오디오 파일을 찾을 수 없습니다.")

    file_name = Path(audio_path).name
    with open(audio_path, "rb") as audio_stream:
        from django.core.files.uploadedfile import SimpleUploadedFile

        file_content = audio_stream.read()
        uploaded_file = SimpleUploadedFile(
            name=file_name,
            content=file_content,
            content_type="audio/wav",
        )

    return analyze_waveform_envelope(
        uploaded_file,
        peak_sensitivity=peak_sensitivity,
        merge_window_ms=merge_window_ms,
        valley_ratio=valley_ratio,
        run_transcription=run_transcription,
        target_peak_count=target_peak_count,
    )


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


# ── Number Counting Analysis ──────────────────────────────────────────────────

def analyze_number_counting(
    uploaded_file,
    peak_sensitivity=DEFAULT_PEAK_SENSITIVITY,
    merge_window_ms=DEFAULT_MERGE_WINDOW_MS,
    valley_ratio=DEFAULT_VALLEY_RATIO,
) -> dict:
    """Analyze a number-counting audio file.

    Returns envelope-based peak detection (each peak ≈ one spoken number)
    plus a spectrogram and matched audio_record_id.
    """
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

        # Amplitude envelope via Hilbert transform
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

        peak_times = [round(float(i / sample_rate), 4) for i in peak_indexes.tolist()]
        intervals_ms = []
        if len(peak_times) >= 2:
            intervals_ms = [
                round((peak_times[i + 1] - peak_times[i]) * 1000.0, 2)
                for i in range(len(peak_times) - 1)
            ]

        peak_count = len(peak_times)
        counting_rate = round(peak_count / duration_seconds, 3) if duration_seconds > 0 else 0.0
        avg_interval_ms = round(float(np.mean(intervals_ms)), 2) if intervals_ms else None
        std_interval_ms = round(float(np.std(intervals_ms)), 2) if len(intervals_ms) >= 2 else None

        matched_audio_record = _match_audio_record_by_filename(uploaded_file.name)
        speaker_info = _build_speaker_info(matched_audio_record)

        spectrogram = _compute_spectrogram(waveform, sample_rate)

        return {
            "file_name": uploaded_file.name,
            "speaker_info": speaker_info,
            "audio_record_id": matched_audio_record.id if matched_audio_record else None,
            "audio_preview_url": preview_audio_url,
            "sample_rate": int(sample_rate),
            "duration_seconds": round(duration_seconds, 3),
            "peak_sensitivity": round(float(peak_sensitivity), 2),
            "merge_window_ms": int(merge_window_ms),
            "valley_ratio": round(float(valley_ratio), 2),
            "peak_count": peak_count,
            "counting_rate": counting_rate,
            "avg_interval_ms": avg_interval_ms,
            "std_interval_ms": std_interval_ms,
            "peak_times": peak_times,
            "intervals_ms": intervals_ms,
            "zoom_enabled": duration_seconds > 10.0,
            "waveform_points": [round(float(v), 6) for v in normalized_waveform.tolist()],
            "waveform_times": [round(float(v), 4) for v in display_waveform_times.tolist()],
            "envelope_points": [round(float(v), 6) for v in normalized_envelope.tolist()],
            "envelope_times": [round(float(v), 4) for v in display_envelope_times.tolist()],
            "spectrogram": spectrogram,
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def reanalyze_number_counting(
    audio_preview_url: str,
    peak_sensitivity=DEFAULT_PEAK_SENSITIVITY,
    merge_window_ms=DEFAULT_MERGE_WINDOW_MS,
    valley_ratio=DEFAULT_VALLEY_RATIO,
) -> dict:
    audio_path = resolve_preview_audio_path(audio_preview_url)
    if not audio_path:
        raise ValueError("오디오 파일을 찾을 수 없습니다.")

    file_name = Path(audio_path).name
    with open(audio_path, "rb") as f:
        from django.core.files.uploadedfile import SimpleUploadedFile
        uploaded_file = SimpleUploadedFile(
            name=file_name,
            content=f.read(),
            content_type="audio/wav",
        )

    result = analyze_number_counting(
        uploaded_file,
        peak_sensitivity=peak_sensitivity,
        merge_window_ms=merge_window_ms,
        valley_ratio=valley_ratio,
    )
    result["audio_preview_url"] = audio_preview_url
    return result


_KFALIGNER_DIR = "/var/www/html/kfaligner"
_KFALIGNER_LOCK = threading.Lock()  # serialize to avoid BIN_DIR write races

# ── MFA (Montreal Forced Aligner) — Korean ────────────────────────────────────
# The Django process already runs inside the `aligner` conda env, so the `mfa`
# binary and Korean models are available directly. Models are referenced by
# absolute path so resolution does not depend on $HOME.
_MFA_BIN = "/home/tyoon/anaconda3/envs/aligner/bin/mfa"
_MFA_ACOUSTIC = "/home/tyoon/Documents/MFA/pretrained_models/acoustic/korean_mfa.zip"
_MFA_DICTIONARY = "/home/tyoon/Documents/MFA/pretrained_models/dictionary/korean_mfa.dict"
_MFA_LOCK = threading.Lock()  # serialize MFA runs (shared temp/model state)


def _parse_textgrid_words_long(textgrid_path: str, tier_name: str = "words") -> list:
    """Parse a named IntervalTier from a long-format Praat TextGrid (MFA output).

    MFA emits long-format TextGrids with named tiers ("words", "phones").
    Returns a list of {word, start, end, score} dicts, excluding empty labels.
    """
    try:
        with open(textgrid_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []

    # Locate the target tier block, then read its intervals until the next item.
    name_marker = f'name = "{tier_name}"'
    name_pos = content.find(name_marker)
    if name_pos == -1:
        return []
    tier_block = content[name_pos:]
    # Stop at the start of the next tier item, if any.
    next_item = re.search(r"\n\s*item \[\d+\]:", tier_block)
    if next_item:
        tier_block = tier_block[: next_item.start()]

    segments = []
    interval_pattern = re.compile(
        r"intervals \[\d+\]:\s*"
        r"xmin = ([\d.]+)\s*"
        r"xmax = ([\d.]+)\s*"
        r'text = "(.*?)"',
        re.DOTALL,
    )
    for match in interval_pattern.finditer(tier_block):
        start = float(match.group(1))
        end = float(match.group(2))
        label = match.group(3).strip()
        if label and label.lower() not in ("sil", "sp", "spn", "<eps>"):
            segments.append({
                "word": label,
                "start": round(start, 4),
                "end": round(end, 4),
                "score": 1.0,
            })
    return segments


def _align_with_mfa(audio_path: str, transcription: str) -> list:
    """Run MFA Korean forced alignment for one audio + transcript.

    Returns word_segments (list of {word, start, end, score}) or [] on failure.
    """
    if not os.path.isfile(_MFA_BIN) or not os.path.isfile(_MFA_ACOUSTIC):
        return []

    with tempfile.TemporaryDirectory() as tmpdir:
        corpus_dir = os.path.join(tmpdir, "corpus")
        output_dir = os.path.join(tmpdir, "out")
        mfa_home = os.path.join(tmpdir, "mfa_root")
        os.makedirs(corpus_dir, exist_ok=True)
        os.makedirs(mfa_home, exist_ok=True)

        shutil.copyfile(audio_path, os.path.join(corpus_dir, "sample.wav"))
        with open(os.path.join(corpus_dir, "sample.lab"), "w", encoding="utf-8") as fh:
            fh.write(transcription.strip() + "\n")

        env = os.environ.copy()
        # Keep MFA's working/cache state inside the temp dir for isolation.
        env["MFA_ROOT_DIR"] = mfa_home

        with _MFA_LOCK:
            proc = subprocess.run(
                [
                    _MFA_BIN, "align", "--clean", "--single_speaker",
                    corpus_dir, _MFA_DICTIONARY, _MFA_ACOUSTIC, output_dir,
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )

        textgrid_path = os.path.join(output_dir, "sample.TextGrid")
        if proc.returncode == 0 and os.path.isfile(textgrid_path):
            return _parse_textgrid_words_long(textgrid_path, tier_name="words")
    return []


def _parse_textgrid_words(textgrid_path: str) -> list:
    """Parse the word tier (3rd IntervalTier) from a short-format Praat TextGrid.

    Returns a list of {word, start, end, score} dicts, excluding sil/sp/empty labels.
    """
    try:
        with open(textgrid_path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\r\n") for ln in f]
    except Exception:
        return []

    tier_idx = 0
    i = 0
    while i < len(lines):
        if lines[i].strip() == '"IntervalTier"':
            tier_idx += 1
            if tier_idx == 3:  # word tier (1=phone, 2=syllable, 3=word, 4=utterance)
                # lines[i]   = "IntervalTier"
                # lines[i+1] = "word"  (tier name)
                # lines[i+2] = xmin
                # lines[i+3] = xmax
                # lines[i+4] = interval count
                i += 4
                try:
                    n = int(lines[i].strip())
                    i += 1
                    segments = []
                    for _ in range(n):
                        start = float(lines[i].strip()); i += 1
                        end   = float(lines[i].strip()); i += 1
                        label = lines[i].strip().strip('"'); i += 1
                        if label and label.lower() not in ("sil", "sp"):
                            segments.append({
                                "word":  label,
                                "start": round(start, 4),
                                "end":   round(end, 4),
                                "score": 1.0,
                            })
                    return segments
                except (ValueError, IndexError):
                    break
        i += 1
    return []


def align_number_counting_audio(audio_preview_url: str) -> dict:
    """Run forced alignment on a number-counting preview audio.

    Strategy:
    1. Transcribe + align with WhisperX (primary).
    2. Transcribe with openai-whisper (needed by the forced aligners below).
    3. MFA (Montreal Forced Aligner) Korean forced alignment.
    4. Fall back to kfaligner (HTK HMM) if MFA fails.
    5. Fall back to openai-whisper word_timestamps if kfaligner also fails.

    Returns:
        {success, word_segments, transcription, error, backend}
        Each word_segment: {word, start, end, score}
    """
    audio_path = resolve_preview_audio_path(audio_preview_url)
    if not audio_path:
        return {"success": False, "error": "오디오 파일을 찾을 수 없습니다.", "word_segments": [], "transcription": ""}

    # ── Step 1: WhisperX (primary) ────────────────────────────────────────
    try:
        import importlib.util as _ilu
        if _ilu.find_spec("whisperx") is not None:
            import whisperx
            import torch
            from django.conf import settings

            cfg = getattr(settings, "WHISPERX_CONFIG", {})
            model_size   = cfg.get("MODEL_SIZE", "large-v3")
            device       = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = cfg.get("COMPUTE_TYPE", "int8")
            language     = cfg.get("FORCE_LANGUAGE") or cfg.get("LANGUAGE") or "ko"

            wx_model = whisperx.load_model(model_size, device=device, compute_type=compute_type)
            audio    = whisperx.load_audio(audio_path)
            result   = wx_model.transcribe(audio, language=language, batch_size=cfg.get("BATCH_SIZE", 16))

            transcription = " ".join(seg.get("text", "") for seg in result.get("segments", [])).strip()

            # Word-level alignment
            align_model, metadata = whisperx.load_align_model(language_code=language, device=device)
            result = whisperx.align(
                result["segments"], align_model, metadata, audio, device,
                return_char_alignments=False,
            )

            word_segments = []
            for seg in result.get("segments", []):
                for w in seg.get("words", []):
                    word = w.get("word", "").strip()
                    start = w.get("start")
                    end   = w.get("end")
                    if word and start is not None and end is not None:
                        word_segments.append({
                            "word":  word,
                            "start": round(float(start), 4),
                            "end":   round(float(end),   4),
                            "score": round(float(w.get("score", 1.0)), 4),
                        })

            if word_segments:
                return {
                    "success": True,
                    "error": None,
                    "transcription": transcription,
                    "word_segments": word_segments,
                    "backend": "whisperx",
                }
    except Exception:
        pass  # fall through to kfaligner

    # ── Step 2: Transcription via openai-whisper (needed for kfaligner) ──
    transcription = ""
    try:
        from voice_app.whisper_utils import get_whisper_model, FORCED_LANGUAGE, INITIAL_PROMPT_KO
        model = get_whisper_model()
        if model is None:
            raise RuntimeError("Whisper 모델을 로드할 수 없습니다.")
        try:
            audio_array_step2 = librosa.load(audio_path, sr=16000, mono=True)[0]
        except Exception:
            audio_array_step2 = audio_path
        raw = model.transcribe(
            audio_array_step2,
            language=FORCED_LANGUAGE,
            initial_prompt=INITIAL_PROMPT_KO,
            verbose=False,
        )
        transcription = " ".join(seg.get("text", "") for seg in raw.get("segments", [])).strip()
    except Exception as exc:
        return {"success": False, "error": f"Whisper 전사 실패: {exc}", "word_segments": [], "transcription": ""}

    if not transcription:
        return {"success": False, "error": "전사된 텍스트가 없습니다.", "word_segments": [], "transcription": ""}

    # ── Step 3: MFA (Montreal Forced Aligner) — Korean ───────────────────
    try:
        mfa_segments = _align_with_mfa(audio_path, transcription)
        if mfa_segments:
            return {
                "success": True,
                "error": None,
                "transcription": transcription,
                "word_segments": mfa_segments,
                "backend": "mfa",
            }
    except Exception:
        pass  # fall through to kfaligner

    # ── Step 4: kfaligner forced alignment ───────────────────────────────
    align_script = os.path.join(_KFALIGNER_DIR, "align.py")
    kfa_tmp_dir  = os.path.join(_KFALIGNER_DIR, "tmp")

    if os.path.isfile(align_script):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                txt_path      = os.path.join(tmpdir, "transcript.txt")
                textgrid_path = os.path.join(tmpdir, "output.TextGrid")

                with open(txt_path, "w", encoding="utf-8") as fh:
                    fh.write(transcription + "\n")

                env = os.environ.copy()
                env["KFALIGNER_TMPDIR"] = kfa_tmp_dir

                with _KFALIGNER_LOCK:
                    os.makedirs(kfa_tmp_dir, exist_ok=True)
                    proc = subprocess.run(
                        [sys.executable, align_script,
                         audio_path, txt_path, textgrid_path],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )

                if proc.returncode == 0 and os.path.isfile(textgrid_path):
                    word_segments = _parse_textgrid_words(textgrid_path)
                    if word_segments:
                        return {
                            "success": True,
                            "error": None,
                            "transcription": transcription,
                            "word_segments": word_segments,
                            "backend": "kfaligner",
                        }
        except Exception:
            pass  # fall through to whisper word_timestamps

    # ── Step 5: Fallback — openai-whisper word_timestamps ────────────────
    try:
        from voice_app.whisper_utils import get_whisper_model, FORCED_LANGUAGE, INITIAL_PROMPT_KO
        model = get_whisper_model()
        if model is None:
            return {"success": False, "error": "Whisper 모델을 로드할 수 없습니다.", "word_segments": [], "transcription": transcription}

        # Pre-load audio as numpy array (16 kHz mono) to bypass PyAV internal
        # loading that may fail with newer av library versions when word_timestamps=True.
        try:
            audio_array = librosa.load(audio_path, sr=16000, mono=True)[0]
        except Exception:
            audio_array = audio_path  # fallback to file path if librosa fails

        result = model.transcribe(
            audio_array,
            language=FORCED_LANGUAGE,
            word_timestamps=True,
            initial_prompt=INITIAL_PROMPT_KO,
            verbose=False,
        )

        word_segments = []
        transcription_parts = []
        for seg in result.get("segments", []):
            transcription_parts.append(seg.get("text", ""))
            for w in seg.get("words", []):
                word_segments.append({
                    "word":  w.get("word", "").strip(),
                    "start": round(float(w.get("start", 0)), 4),
                    "end":   round(float(w.get("end", 0)), 4),
                    "score": round(float(w.get("probability", 0)), 4),
                })

        return {
            "success": True,
            "error": None,
            "transcription": " ".join(transcription_parts).strip(),
            "word_segments": word_segments,
            "backend": "whisper",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "word_segments": [], "transcription": transcription}