from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

import io
import wave
import numpy as np
from unittest.mock import patch

from voice_app.models import AudioRecord

from .services import (
    _merge_nearby_peaks,
    analyze_sustained_vowel_segment,
    analyze_audio_record,
    analyze_waveform_envelope,
    analyze_waveform_only,
    normalize_merge_window_ms,
    constrain_transcript_token_count,
    constrain_whisper_transcript,
    normalize_peak_sensitivity,
    reanalyze_waveform_only,
    normalize_valley_ratio,
    resolve_preview_audio_path,
)


def build_wav_file_bytes(sample_rate=16000, duration_seconds=1.0):
    import math
    import struct

    sample_count = int(sample_rate * duration_seconds)
    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = []
        for index in range(sample_count):
            time_position = index / sample_rate
            amplitude = 0.85 if int(time_position * 4) % 2 == 0 else 0.2
            sample = amplitude * math.sin(2 * math.pi * 220 * time_position)
            frames.append(struct.pack("<h", int(sample * 32767)))

        wav_file.writeframes(b"".join(frames))

    return buffer.getvalue()


class VoiceAnalysisServiceTests(TestCase):
    def test_basic_analysis_creates_result_from_audio_record(self):
        audio_record = AudioRecord.objects.create(
            audio_file="audio/test.wav",
            category="normal",
            identifier="A12345",
            transcript="테스트 전사",
            status="completed",
        )

        analysis = analyze_audio_record(audio_record)

        self.assertEqual(analysis.status, "completed")
        self.assertEqual(analysis.analysis_type, "basic")
        self.assertEqual(analysis.result_data["audio_record_id"], audio_record.id)
        self.assertTrue(analysis.result_data["has_transcript"])


class VoiceAnalysisViewTests(TestCase):
    def test_index_page_renders_landing_page(self):
        response = self.client.get(reverse("voice_analysis:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KASPER Voice Analysis")
        self.assertContains(response, "sustained a 분석")
        self.assertContains(response, reverse("voice_analysis:sustained_vowel_analysis"))
        self.assertContains(response, "DDK 분석")
        self.assertContains(response, reverse("voice_analysis:ddk_analysis"))
        self.assertTemplateUsed(response, "voice_analysis/index.html")

    def test_sustained_vowel_analysis_page_renders_placeholder(self):
        response = self.client.get(reverse("voice_analysis:sustained_vowel_analysis"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sustained Vowel Analysis")
        self.assertContains(response, "오디오 파일 선택")
        self.assertContains(response, "분석 실행")
        self.assertTemplateUsed(response, "voice_analysis/sustained_vowel_analysis.html")

    def test_sustained_vowel_selection_analysis_runs_from_selected_range(self):
        audio_file = SimpleUploadedFile(
            "sustained.wav",
            build_wav_file_bytes(duration_seconds=1.4),
            content_type="audio/wav",
        )

        upload_response = self.client.post(
            reverse("voice_analysis:sustained_vowel_analysis"),
            {"audio_file": audio_file},
        )
        self.assertEqual(upload_response.status_code, 200)
        analysis = upload_response.context["analysis_result"]

        segment_response = self.client.post(
            reverse("voice_analysis:sustained_vowel_analysis"),
            {
                "action": "analyze_segment",
                "audio_preview_url": analysis["audio_preview_url"],
                "selection_start": "0.20",
                "selection_end": "0.80",
            },
        )

        self.assertEqual(segment_response.status_code, 200)
        self.assertContains(segment_response, "선택 구간 분석 결과")
        self.assertContains(segment_response, "Duration (ms)")
        self.assertContains(segment_response, "F1 (Hz)")
        self.assertContains(segment_response, "F2 (Hz)")
        self.assertContains(segment_response, "Shimmer (local)")
        self.assertContains(segment_response, "Jitter (local)")
        self.assertContains(segment_response, "HNR (dB)")
        self.assertContains(segment_response, "CPP")
        self.assertContains(segment_response, "Peak Period (ms)")
        self.assertContains(segment_response, "Estimated F0 (Hz)")
        self.assertContains(segment_response, "Cepstral Analysis")
        self.assertContains(segment_response, "cepstral-chart")

    def test_ddk_analysis_page_renders_analysis_template(self):
        response = self.client.get(reverse("voice_analysis:ddk_analysis"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Voice Envelope Analysis")
        self.assertTemplateUsed(response, "voice_analysis/ddk_analysis.html")

    def test_help_periodicity_page_renders(self):
        response = self.client.get(reverse("voice_analysis:help_periodicity"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Periodicity Help")
        self.assertContains(response, "katex.min.css")
        self.assertTemplateUsed(response, "voice_analysis/help_periodicity.html")

    def test_index_page_analyzes_uploaded_audio(self):
        audio_file = SimpleUploadedFile(
            "sample.wav",
            build_wav_file_bytes(),
            content_type="audio/wav",
        )

        response = self.client.post(
            reverse("voice_analysis:ddk_analysis"),
            {"audio_file": audio_file},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Envelope Peak 개수")
        self.assertContains(response, "sample.wav")
        self.assertContains(response, "Original waveform")
        self.assertContains(response, "현재 확대 구간 Peak")
        self.assertContains(response, "현재 확대 구간 Periodicity")
        self.assertContains(response, reverse("voice_analysis:help_periodicity"))
        self.assertContains(response, "periodicity-period")
        self.assertContains(response, "reset-removed-peaks")
        self.assertContains(response, "차트의 빨간 점을 클릭하면")
        self.assertContains(response, "play-selection")
        self.assertContains(response, "선택 구간 재생")
        self.assertContains(response, "Whisper 전사를 선택하지 않아 결과를 표시하지 않습니다.")
        self.assertContains(response, "화자 정보")
        self.assertContains(response, "파일명으로 매칭된 화자 정보가 없습니다.")
        self.assertNotContains(response, "Zoom In")

    def test_ddk_analysis_uses_wav_file_name_to_show_speaker_info(self):
        AudioRecord.objects.create(
            audio_file="audio/normal/S12345/sample.wav",
            category="normal",
            identifier="S12345",
            name="홍길동",
            gender="남",
            birth_year="2010",
            birth_month="1",
            birth_day="9",
            region="서울",
            recording_location="병원",
            diagnosis="없음",
        )

        audio_file = SimpleUploadedFile(
            "sample.wav",
            build_wav_file_bytes(),
            content_type="audio/wav",
        )

        response = self.client.post(
            reverse("voice_analysis:ddk_analysis"),
            {"audio_file": audio_file},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "홍길동")
        self.assertContains(response, "S12345")
        self.assertContains(response, "서울")
        self.assertContains(response, "2010-01-09")

    def test_ddk_analysis_accepts_audio_preview_url_without_upload(self):
        uploaded_file = SimpleUploadedFile(
            "source.wav",
            build_wav_file_bytes(duration_seconds=1.2),
            content_type="audio/wav",
        )
        initial_result = analyze_waveform_only(uploaded_file)

        response = self.client.post(
            reverse("voice_analysis:ddk_analysis"),
            {
                "audio_preview_url": initial_result["audio_preview_url"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Envelope Peak 개수")
        self.assertContains(response, "voice_analysis_preview")

    def test_index_page_uses_requested_peak_sensitivity(self):
        audio_file = SimpleUploadedFile(
            "sensitive.wav",
            build_wav_file_bytes(),
            content_type="audio/wav",
        )

        response = self.client.post(
            reverse("voice_analysis:ddk_analysis"),
            {"audio_file": audio_file, "peak_sensitivity": "0.85"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0.85")
        self.assertContains(response, "total-peak-count")
        self.assertContains(response, "peak-time-list")

    def test_index_page_uses_requested_merge_parameters(self):
        audio_file = SimpleUploadedFile(
            "merge.wav",
            build_wav_file_bytes(),
            content_type="audio/wav",
        )

        response = self.client.post(
            reverse("voice_analysis:ddk_analysis"),
            {
                "audio_file": audio_file,
                "merge_window_ms": "180",
                "valley_ratio": "0.44",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "180")
        self.assertContains(response, "0.44")

    @patch("voice_app.whisper_utils.transcribe_audio", return_value="퍼 터 커")
    def test_retranscribe_action_applies_target_peak_count(self, mocked_transcribe):
        audio_file = SimpleUploadedFile(
            "sample.wav",
            build_wav_file_bytes(),
            content_type="audio/wav",
        )

        first_response = self.client.post(
            reverse("voice_analysis:ddk_analysis"),
            {"audio_file": audio_file, "run_transcription": "on"},
        )

        self.assertEqual(first_response.status_code, 200)
        analysis = first_response.context["analysis_result"]
        self.assertTrue(analysis["audio_preview_url"])

        second_response = self.client.post(
            reverse("voice_analysis:ddk_analysis"),
            {
                "action": "retranscribe",
                "audio_preview_url": analysis["audio_preview_url"],
                "peak_sensitivity": "0.5",
                "target_peak_count": "2",
                "run_transcription": "on",
            },
        )

        self.assertEqual(second_response.status_code, 200)
        retranscribed = second_response.context["analysis_result"]
        self.assertEqual(retranscribed["target_peak_count"], 2)
        self.assertEqual(retranscribed["transcript_text"], "퍼터커 퍼터커")
        mocked_transcribe.assert_called()

    def test_index_page_shows_zoom_controls_for_long_audio(self):
        audio_file = SimpleUploadedFile(
            "long_sample.wav",
            build_wav_file_bytes(duration_seconds=12.0),
            content_type="audio/wav",
        )

        response = self.client.post(
            reverse("voice_analysis:ddk_analysis"),
            {"audio_file": audio_file},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zoom In")
        self.assertContains(response, "Zoom Out")


class WaveformEnvelopeAnalysisTests(TestCase):
    def test_merge_nearby_peaks_collapses_double_peak_in_same_vowel(self):
        envelope = np.array([0.05, 0.2, 0.7, 0.62, 0.75, 0.2, 0.05], dtype=np.float32)
        peaks = np.array([2, 4], dtype=int)

        merged = _merge_nearby_peaks(
            peak_indexes=peaks,
            envelope_values=envelope,
            sample_rate=100,
            peak_sensitivity=0.5,
        )

        self.assertEqual(merged.tolist(), [4])

    def test_normalize_peak_sensitivity_clamps_to_valid_range(self):
        self.assertEqual(normalize_peak_sensitivity("bad"), 0.5)
        self.assertEqual(normalize_peak_sensitivity(-1), 0.05)
        self.assertEqual(normalize_peak_sensitivity(2), 1.0)

    def test_merge_parameter_normalization_clamps_to_valid_range(self):
        self.assertEqual(normalize_merge_window_ms("bad"), 120)
        self.assertEqual(normalize_merge_window_ms(999), 240)
        self.assertEqual(normalize_valley_ratio("bad"), 0.58)
        self.assertEqual(normalize_valley_ratio(0.05), 0.30)
        self.assertEqual(normalize_valley_ratio(2), 0.95)

    def test_waveform_envelope_returns_points_and_peak_count(self):
        uploaded_file = SimpleUploadedFile(
            "burst.wav",
            build_wav_file_bytes(duration_seconds=1.2),
            content_type="audio/wav",
        )

        result = analyze_waveform_envelope(uploaded_file)

        self.assertEqual(result["file_name"], "burst.wav")
        self.assertGreater(len(result["waveform_points"]), 0)
        self.assertEqual(len(result["waveform_points"]), len(result["waveform_times"]))
        self.assertGreater(len(result["envelope_points"]), 0)
        self.assertEqual(len(result["envelope_points"]), len(result["envelope_times"]))
        self.assertGreaterEqual(result["peak_count"], 1)
        self.assertFalse(result["zoom_enabled"])
        self.assertEqual(result["peak_sensitivity"], 0.5)
        self.assertEqual(result["merge_window_ms"], 120)
        self.assertEqual(result["valley_ratio"], 0.58)
        self.assertIn("voice_analysis_preview", result["audio_preview_url"])
        self.assertFalse(result["transcription_enabled"])

    @patch("voice_app.whisper_utils.transcribe_audio", return_value="퍼 터 커 퍼터커")
    def test_waveform_envelope_returns_transcription_summary(self, mocked_transcribe):
        uploaded_file = SimpleUploadedFile(
            "speak.wav",
            build_wav_file_bytes(duration_seconds=1.2),
            content_type="audio/wav",
        )

        result = analyze_waveform_envelope(uploaded_file, run_transcription=True)

        self.assertTrue(result["transcription_enabled"])
        self.assertEqual(result["transcript_text"], "퍼터커 퍼터커")
        self.assertEqual(result["transcript_summary"]["퍼터커"], 2)
        self.assertEqual(result["transcript_summary"]["퍼"], 0)
        self.assertEqual(result["transcript_summary"]["터"], 0)
        self.assertEqual(result["transcript_summary"]["커"], 0)
        mocked_transcribe.assert_called_once()

    def test_constrain_whisper_transcript_keeps_only_allowed_tokens(self):
        constrained = constrain_whisper_transcript("파 타 카 파타카 버 더 거")

        self.assertEqual(constrained, "퍼터커 퍼터커 퍼터커")

    def test_constrain_transcript_token_count_matches_target(self):
        constrained = constrain_transcript_token_count("퍼터커 퍼터커 퍼터커", 2)
        expanded = constrain_transcript_token_count("퍼터커", 3)

        self.assertEqual(constrained, "퍼터커 퍼터커")
        self.assertEqual(expanded, "퍼터커 퍼터커 퍼터커")

    def test_resolve_preview_audio_path_rejects_outside_media(self):
        self.assertEqual(resolve_preview_audio_path("/etc/passwd"), "")

    @patch("voice_app.whisper_utils.transcribe_audio", return_value="파 타 카 파타카 빠따까")
    def test_waveform_envelope_transcription_applies_eo_vowel_constraint(self, mocked_transcribe):
        uploaded_file = SimpleUploadedFile(
            "constraint.wav",
            build_wav_file_bytes(duration_seconds=1.2),
            content_type="audio/wav",
        )

        result = analyze_waveform_envelope(uploaded_file, run_transcription=True)

        self.assertEqual(result["transcript_text"], "퍼터커 퍼터커 퍼터커")
        self.assertEqual(result["transcript_summary"]["퍼터커"], 3)
        self.assertEqual(result["transcript_summary"]["퍼"], 0)
        self.assertEqual(result["transcript_summary"]["터"], 0)
        self.assertEqual(result["transcript_summary"]["커"], 0)
        mocked_transcribe.assert_called_once()

    def test_waveform_envelope_accepts_custom_peak_sensitivity(self):
        uploaded_file = SimpleUploadedFile(
            "sensitivity.wav",
            build_wav_file_bytes(duration_seconds=1.2),
            content_type="audio/wav",
        )

        result = analyze_waveform_envelope(uploaded_file, peak_sensitivity=0.85)

        self.assertEqual(result["peak_sensitivity"], 0.85)
        self.assertGreaterEqual(result["peak_count"], 1)

    def test_waveform_envelope_accepts_custom_merge_parameters(self):
        uploaded_file = SimpleUploadedFile(
            "merge_tune.wav",
            build_wav_file_bytes(duration_seconds=1.2),
            content_type="audio/wav",
        )

        result = analyze_waveform_envelope(
            uploaded_file,
            merge_window_ms=180,
            valley_ratio=0.42,
        )

        self.assertEqual(result["merge_window_ms"], 180)
        self.assertEqual(result["valley_ratio"], 0.42)

    def test_waveform_envelope_enables_zoom_for_long_audio(self):
        uploaded_file = SimpleUploadedFile(
            "long_burst.wav",
            build_wav_file_bytes(duration_seconds=12.0),
            content_type="audio/wav",
        )

        result = analyze_waveform_envelope(uploaded_file)

        self.assertTrue(result["zoom_enabled"])

    def test_sustained_vowel_segment_metrics_are_calculated(self):
        uploaded_file = SimpleUploadedFile(
            "sustained_segment.wav",
            build_wav_file_bytes(duration_seconds=1.6),
            content_type="audio/wav",
        )

        waveform_result = analyze_waveform_only(uploaded_file)
        restored = reanalyze_waveform_only(waveform_result["audio_preview_url"])
        segment_result = analyze_sustained_vowel_segment(
            audio_preview_url=restored["audio_preview_url"],
            start_seconds=0.25,
            end_seconds=0.95,
        )

        self.assertGreater(segment_result["duration_ms"], 0)
        self.assertIn("f1_hz", segment_result)
        self.assertIn("f2_hz", segment_result)
        self.assertIn("jitter_local", segment_result)
        self.assertIn("shimmer_local", segment_result)
        self.assertIn("hnr_db", segment_result)
        self.assertIn("cpp", segment_result)
        self.assertIn("cepstrum_profile", segment_result)
        self.assertTrue(segment_result["cepstrum_profile"].get("quefrency_ms"))
        self.assertTrue(segment_result["cepstrum_profile"].get("magnitude_db"))
        self.assertTrue(segment_result["cepstrum_profile"].get("regression_db"))
        self.assertIsNotNone(segment_result["cepstrum_profile"].get("peak_period_ms"))
        self.assertIsNotNone(segment_result["cepstrum_profile"].get("peak_frequency_hz"))