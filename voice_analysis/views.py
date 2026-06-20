import json

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import VoiceAnalysis
from .services import (
    DEFAULT_MERGE_WINDOW_MS,
    DEFAULT_PEAK_SENSITIVITY,
    DEFAULT_VALLEY_RATIO,
    analyze_waveform_envelope,
    analyze_sustained_vowel_segment,
    analyze_waveform_only,
    analyze_waveform_envelope_from_url,
    analyze_number_counting,
    reanalyze_number_counting,
    align_number_counting_audio,
    normalize_merge_window_ms,
    normalize_peak_sensitivity,
    normalize_valley_ratio,
    reanalyze_waveform_only,
    reanalyze_saved_audio,
    _match_audio_record_by_filename,
    _load_saved_vowel_markers,
)


def index(request):
    return render(request, "voice_analysis/index.html")


def sustained_vowel_analysis(request):
    context = {
        "analysis_result": None,
        "segment_result": None,
        "error_message": "",
    }

    if request.method == "POST":
        action = request.POST.get("action", "analyze")
        if action == "analyze_segment":
            audio_preview_url = request.POST.get("audio_preview_url", "")
            selection_start = request.POST.get("selection_start", "")
            selection_end = request.POST.get("selection_end", "")
            raw_marker_onset  = request.POST.get("marker_onset", "").strip()
            raw_marker_offset = request.POST.get("marker_offset", "").strip()

            try:
                result = reanalyze_waveform_only(audio_preview_url, include_spectrogram=True)
                # Explicit form values take priority; fall back to DB-saved markers
                if raw_marker_onset and raw_marker_offset:
                    try:
                        result["vowel_onset"]  = round(float(raw_marker_onset), 4)
                        result["vowel_offset"] = round(float(raw_marker_offset), 4)
                    except ValueError:
                        pass
                else:
                    saved = _load_saved_vowel_markers(result.get("audio_record_id"))
                    if saved:
                        result["vowel_onset"]  = saved["onset"]
                        result["vowel_offset"] = saved["offset"]
                context["analysis_result"] = result
                context["segment_result"] = analyze_sustained_vowel_segment(
                    audio_preview_url=audio_preview_url,
                    start_seconds=selection_start,
                    end_seconds=selection_end,
                )
            except Exception as exc:
                context["error_message"] = f"선택 구간 분석에 실패했습니다: {exc}"

            return render(request, "voice_analysis/sustained_vowel_analysis.html", context)

        uploaded_file = request.FILES.get("audio_file")
        audio_preview_url = request.POST.get("audio_preview_url", "").strip()

        if uploaded_file is not None:
            try:
                result = analyze_waveform_only(uploaded_file, include_spectrogram=True)
                saved = _load_saved_vowel_markers(result.get("audio_record_id"))
                if saved:
                    result["vowel_onset"]  = saved["onset"]
                    result["vowel_offset"] = saved["offset"]
                context["analysis_result"] = result
            except Exception as exc:
                context["error_message"] = f"음성 분석에 실패했습니다: {exc}"
        elif audio_preview_url:
            try:
                result = reanalyze_waveform_only(audio_preview_url, include_spectrogram=True)
                saved = _load_saved_vowel_markers(result.get("audio_record_id"))
                if saved:
                    result["vowel_onset"]  = saved["onset"]
                    result["vowel_offset"] = saved["offset"]
                context["analysis_result"] = result
            except Exception as exc:
                context["error_message"] = f"음성 분석에 실패했습니다: {exc}"
        else:
            context["error_message"] = "분석할 음성 파일을 선택해 주세요."

    return render(request, "voice_analysis/sustained_vowel_analysis.html", context)


def ddk_analysis(request):
    context = {
        "analysis_result": None,
        "error_message": "",
        "peak_sensitivity": DEFAULT_PEAK_SENSITIVITY,
        "merge_window_ms": DEFAULT_MERGE_WINDOW_MS,
        "valley_ratio": DEFAULT_VALLEY_RATIO,
        "run_transcription": True,
    }

    if request.method == "POST":
        action = request.POST.get("action", "analyze")
        uploaded_file = request.FILES.get("audio_file")
        audio_preview_url = request.POST.get("audio_preview_url", "").strip()
        peak_sensitivity = normalize_peak_sensitivity(request.POST.get("peak_sensitivity"))
        merge_window_ms = normalize_merge_window_ms(request.POST.get("merge_window_ms"))
        valley_ratio = normalize_valley_ratio(request.POST.get("valley_ratio"))
        run_transcription = request.POST.get("run_transcription") == "on"
        context["peak_sensitivity"] = peak_sensitivity
        context["merge_window_ms"] = merge_window_ms
        context["valley_ratio"] = valley_ratio
        context["run_transcription"] = run_transcription

        if action == "retranscribe":
            audio_preview_url = request.POST.get("audio_preview_url", "")
            raw_target_peak_count = request.POST.get("target_peak_count")
            target_peak_count = None
            if raw_target_peak_count not in (None, ""):
                try:
                    target_peak_count = max(int(raw_target_peak_count), 0)
                except (TypeError, ValueError):
                    target_peak_count = None

            try:
                context["analysis_result"] = reanalyze_saved_audio(
                    audio_preview_url=audio_preview_url,
                    peak_sensitivity=peak_sensitivity,
                    merge_window_ms=merge_window_ms,
                    valley_ratio=valley_ratio,
                    run_transcription=True,
                    target_peak_count=target_peak_count,
                )
            except Exception as exc:
                context["error_message"] = f"재전사에 실패했습니다: {exc}"

            return render(request, "voice_analysis/ddk_analysis.html", context)

        if uploaded_file is not None:
            try:
                context["analysis_result"] = analyze_waveform_envelope(
                    uploaded_file,
                    peak_sensitivity=peak_sensitivity,
                    merge_window_ms=merge_window_ms,
                    valley_ratio=valley_ratio,
                    run_transcription=run_transcription,
                )
            except Exception as exc:
                context["error_message"] = f"음성 분석에 실패했습니다: {exc}"
        elif audio_preview_url:
            try:
                context["analysis_result"] = analyze_waveform_envelope_from_url(
                    audio_preview_url=audio_preview_url,
                    peak_sensitivity=peak_sensitivity,
                    merge_window_ms=merge_window_ms,
                    valley_ratio=valley_ratio,
                    run_transcription=run_transcription,
                )
            except Exception as exc:
                context["error_message"] = f"음성 분석에 실패했습니다: {exc}"
        else:
            context["error_message"] = "분석할 음성 파일을 선택해 주세요."

    return render(request, "voice_analysis/ddk_analysis.html", context)


def help_periodicity(request):
    return render(request, "voice_analysis/help_ddk_analysis.html")


def help_sustained_vowel_analysis(request):
    return render(request, "voice_analysis/help_sustained_vowel_analysis.html")


def help_number_counting_analysis(request):
    return render(request, "voice_analysis/help_number_counting_analysis.html")


def help_sentence_reading_senior_analysis(request):
    return render(request, "voice_analysis/help_sentence_reading_senior_analysis.html")


def help_paragraph_reading_senior_analysis(request):
    return render(request, "voice_analysis/help_paragraph_reading_senior_analysis.html")


def help_picture_button_analysis(request):
    return render(request, "voice_analysis/help_picture_button_analysis.html")


def help_apac_storytelling_analysis(request):
    return render(request, "voice_analysis/help_apac_storytelling_analysis.html")


def help_storytelling_analysis(request):
    return render(request, "voice_analysis/help_storytelling_analysis.html")


def number_counting_analysis(request):
    context = {
        "default_peak_sensitivity": DEFAULT_PEAK_SENSITIVITY,
        "default_merge_window_ms": DEFAULT_MERGE_WINDOW_MS,
        "default_valley_ratio": DEFAULT_VALLEY_RATIO,
    }
    if request.method != "POST":
        return render(request, "voice_analysis/number_counting_analysis.html", context)

    action = request.POST.get("action", "")

    # ── Re-analyze with updated parameters ────────────────
    if action == "reanalyze":
        audio_preview_url = request.POST.get("audio_preview_url", "")
        peak_sensitivity = normalize_peak_sensitivity(request.POST.get("peak_sensitivity", DEFAULT_PEAK_SENSITIVITY))
        merge_window_ms = normalize_merge_window_ms(request.POST.get("merge_window_ms", DEFAULT_MERGE_WINDOW_MS))
        valley_ratio = normalize_valley_ratio(request.POST.get("valley_ratio", DEFAULT_VALLEY_RATIO))
        try:
            context["analysis_result"] = reanalyze_number_counting(
                audio_preview_url,
                peak_sensitivity=peak_sensitivity,
                merge_window_ms=merge_window_ms,
                valley_ratio=valley_ratio,
            )
        except Exception as exc:
            context["error_message"] = f"재분석에 실패했습니다: {exc}"
        return render(request, "voice_analysis/number_counting_analysis.html", context)

    # ── Initial analysis from URL (audio_detail redirect) ─
    audio_preview_url = request.POST.get("audio_preview_url", "")
    uploaded_file = request.FILES.get("audio_file")

    if uploaded_file is not None:
        try:
            context["analysis_result"] = analyze_number_counting(uploaded_file)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"
    elif audio_preview_url:
        try:
            context["analysis_result"] = reanalyze_number_counting(audio_preview_url)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"

    return render(request, "voice_analysis/number_counting_analysis.html", context)


def picture_button_analysis(request):
    context = {}
    if request.method != "POST":
        return render(request, "voice_analysis/picture_button_analysis.html", context)

    audio_preview_url = request.POST.get("audio_preview_url", "")
    uploaded_file = request.FILES.get("audio_file")

    if uploaded_file is not None:
        try:
            context["analysis_result"] = analyze_number_counting(uploaded_file)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"
    elif audio_preview_url:
        try:
            context["analysis_result"] = reanalyze_number_counting(audio_preview_url)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"

    return render(request, "voice_analysis/picture_button_analysis.html", context)


@require_POST
def picture_button_align(request):
    """AJAX endpoint: run WhisperX forced alignment on a picture-button preview audio."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    audio_preview_url = body.get("audio_preview_url", "").strip()
    if not audio_preview_url:
        return JsonResponse({"success": False, "error": "audio_preview_url이 필요합니다."}, status=400)

    result = align_number_counting_audio(audio_preview_url)
    status_code = 200 if result["success"] else 500
    return JsonResponse(result, status=status_code)


def paragraph_reading_senior_analysis(request):
    context = {}
    if request.method != "POST":
        return render(request, "voice_analysis/paragraph_reading_senior_analysis.html", context)

    audio_preview_url = request.POST.get("audio_preview_url", "")
    uploaded_file = request.FILES.get("audio_file")

    if uploaded_file is not None:
        try:
            context["analysis_result"] = analyze_number_counting(uploaded_file)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"
    elif audio_preview_url:
        try:
            context["analysis_result"] = reanalyze_number_counting(audio_preview_url)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"

    return render(request, "voice_analysis/paragraph_reading_senior_analysis.html", context)


@require_POST
def paragraph_reading_senior_align(request):
    """AJAX endpoint: run WhisperX forced alignment on a paragraph-reading-senior preview audio."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    audio_preview_url = body.get("audio_preview_url", "").strip()
    if not audio_preview_url:
        return JsonResponse({"success": False, "error": "audio_preview_url이 필요합니다."}, status=400)

    result = align_number_counting_audio(audio_preview_url)
    status_code = 200 if result["success"] else 500
    return JsonResponse(result, status=status_code)


def sentence_reading_senior_analysis(request):
    context = {}
    if request.method != "POST":
        return render(request, "voice_analysis/sentence_reading_senior_analysis.html", context)

    audio_preview_url = request.POST.get("audio_preview_url", "")
    uploaded_file = request.FILES.get("audio_file")

    if uploaded_file is not None:
        try:
            context["analysis_result"] = analyze_number_counting(uploaded_file)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"
    elif audio_preview_url:
        try:
            context["analysis_result"] = reanalyze_number_counting(audio_preview_url)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"

    return render(request, "voice_analysis/sentence_reading_senior_analysis.html", context)


@require_POST
def sentence_reading_senior_align(request):
    """AJAX endpoint: run WhisperX forced alignment on a sentence-reading-senior preview audio."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    audio_preview_url = body.get("audio_preview_url", "").strip()
    if not audio_preview_url:
        return JsonResponse({"success": False, "error": "audio_preview_url이 필요합니다."}, status=400)

    result = align_number_counting_audio(audio_preview_url)
    status_code = 200 if result["success"] else 500
    return JsonResponse(result, status=status_code)


@require_POST
def number_counting_align(request):
    """AJAX endpoint: run WhisperX forced alignment on a number-counting preview audio."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    audio_preview_url = body.get("audio_preview_url", "").strip()
    if not audio_preview_url:
        return JsonResponse({"success": False, "error": "audio_preview_url이 필요합니다."}, status=400)

    result = align_number_counting_audio(audio_preview_url)
    status_code = 200 if result["success"] else 500
    return JsonResponse(result, status=status_code)


def storytelling_analysis(request):
    context = {}
    if request.method != "POST":
        return render(request, "voice_analysis/storytelling_analysis.html", context)

    audio_preview_url = request.POST.get("audio_preview_url", "")
    uploaded_file = request.FILES.get("audio_file")

    if uploaded_file is not None:
        try:
            context["analysis_result"] = analyze_number_counting(uploaded_file)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"
    elif audio_preview_url:
        try:
            context["analysis_result"] = reanalyze_number_counting(audio_preview_url)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"

    return render(request, "voice_analysis/storytelling_analysis.html", context)


@require_POST
def storytelling_align(request):
    """AJAX endpoint: run WhisperX forced alignment on a storytelling preview audio."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    audio_preview_url = body.get("audio_preview_url", "").strip()
    if not audio_preview_url:
        return JsonResponse({"success": False, "error": "audio_preview_url이 필요합니다."}, status=400)

    result = align_number_counting_audio(audio_preview_url)
    status_code = 200 if result["success"] else 500
    return JsonResponse(result, status=status_code)


def apac_storytelling_analysis(request):
    context = {}
    if request.method != "POST":
        return render(request, "voice_analysis/apac_storytelling_analysis.html", context)

    audio_preview_url = request.POST.get("audio_preview_url", "")
    uploaded_file = request.FILES.get("audio_file")

    if uploaded_file is not None:
        try:
            context["analysis_result"] = analyze_number_counting(uploaded_file)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"
    elif audio_preview_url:
        try:
            context["analysis_result"] = reanalyze_number_counting(audio_preview_url)
        except Exception as exc:
            context["error_message"] = f"음성 분석에 실패했습니다: {exc}"

    return render(request, "voice_analysis/apac_storytelling_analysis.html", context)


@require_POST
def apac_storytelling_align(request):
    """AJAX endpoint: run WhisperX forced alignment on an APAC storytelling preview audio."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    audio_preview_url = body.get("audio_preview_url", "").strip()
    if not audio_preview_url:
        return JsonResponse({"success": False, "error": "audio_preview_url이 필요합니다."}, status=400)

    result = align_number_counting_audio(audio_preview_url)
    status_code = 200 if result["success"] else 500
    return JsonResponse(result, status=status_code)


@require_POST
def save_vowel_markers(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    audio_record_id = body.get("audio_record_id")
    onset      = body.get("onset")
    offset     = body.get("offset")
    duration_ms = body.get("duration_ms")

    if not audio_record_id or onset is None or offset is None:
        return JsonResponse({"success": False, "error": "audio_record_id, onset, offset가 필요합니다."}, status=400)

    from voice_app.models import AudioRecord
    try:
        audio_record = AudioRecord.objects.get(id=int(audio_record_id))
    except (AudioRecord.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"success": False, "error": "음성 레코드를 찾을 수 없습니다."}, status=404)

    onset_f  = float(onset)
    offset_f = float(offset)
    result_data = {"onset": onset_f, "offset": offset_f}
    if duration_ms is not None:
        try:
            result_data["duration_ms"] = round(float(duration_ms), 1)
        except (ValueError, TypeError):
            pass

    dur_ms = result_data.get("duration_ms")
    summary = f"vowel_marker: onset={onset_f:.4f}s, offset={offset_f:.4f}s"
    if dur_ms is not None:
        summary += f", duration={dur_ms:.1f}ms"

    now = timezone.now()
    VoiceAnalysis.objects.filter(audio_record=audio_record, analysis_type="vowel_marker").delete()
    VoiceAnalysis.objects.create(
        audio_record=audio_record,
        requested_by=request.user if request.user.is_authenticated else None,
        analysis_type="vowel_marker",
        status="completed",
        result_data=result_data,
        summary=summary,
        started_at=now,
        completed_at=now,
    )
    return JsonResponse({"success": True})


@require_POST
def reset_vowel_markers(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    audio_record_id = body.get("audio_record_id")
    if not audio_record_id:
        return JsonResponse({"success": False, "error": "audio_record_id가 필요합니다."}, status=400)

    try:
        VoiceAnalysis.objects.filter(
            audio_record_id=int(audio_record_id),
            analysis_type="vowel_marker",
        ).delete()
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "잘못된 audio_record_id입니다."}, status=400)

    return JsonResponse({"success": True})


@require_POST
def save_ddk_analysis(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "잘못된 요청입니다."}, status=400)

    file_name = body.get("file_name", "")
    audio_preview_url = body.get("audio_preview_url", "")

    try:
        peak_count = int(body.get("peak_count", 0))
    except (TypeError, ValueError):
        peak_count = 0

    peak_sensitivity = normalize_peak_sensitivity(body.get("peak_sensitivity"))
    merge_window_ms = normalize_merge_window_ms(body.get("merge_window_ms"))
    valley_ratio = normalize_valley_ratio(body.get("valley_ratio"))

    try:
        overwrite_id = int(body["overwrite_id"]) if body.get("overwrite_id") is not None else None
    except (TypeError, ValueError):
        overwrite_id = None

    audio_record = _match_audio_record_by_filename(file_name)
    if audio_record is None:
        return JsonResponse(
            {"success": False, "error": "매칭되는 음성 레코드를 찾을 수 없습니다. 파일명이 DB에 등록된 음성과 일치하지 않습니다."},
            status=404,
        )

    result_data = {
        "peak_count": peak_count,
        "peak_sensitivity": float(peak_sensitivity),
        "merge_window_ms": int(merge_window_ms),
        "valley_ratio": float(valley_ratio),
    }
    input_snapshot = {
        "peak_sensitivity": float(peak_sensitivity),
        "merge_window_ms": int(merge_window_ms),
        "valley_ratio": float(valley_ratio),
        "audio_preview_url": audio_preview_url,
    }
    summary = f"DDK 분석: peak_count={peak_count}, peak_sensitivity={peak_sensitivity:.2f}"
    now = timezone.now()

    if overwrite_id is not None:
        updated = VoiceAnalysis.objects.filter(
            id=overwrite_id,
            audio_record=audio_record,
            analysis_type="ddk",
        ).update(
            result_data=result_data,
            input_snapshot=input_snapshot,
            summary=summary,
            completed_at=now,
            updated_at=now,
        )
        if updated:
            return JsonResponse({"success": True, "id": overwrite_id, "message": "분석 결과가 덮어쓰기 되었습니다."})

    analysis = VoiceAnalysis.objects.create(
        audio_record=audio_record,
        requested_by=request.user if request.user.is_authenticated else None,
        analysis_type="ddk",
        status="completed",
        input_snapshot=input_snapshot,
        result_data=result_data,
        summary=summary,
        started_at=now,
        completed_at=now,
    )

    return JsonResponse({"success": True, "id": analysis.id, "message": "분석 결과가 저장되었습니다."})