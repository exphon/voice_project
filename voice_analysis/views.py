from django.shortcuts import render

from .services import (
    DEFAULT_MERGE_WINDOW_MS,
    DEFAULT_PEAK_SENSITIVITY,
    DEFAULT_VALLEY_RATIO,
    analyze_waveform_envelope,
    analyze_sustained_vowel_segment,
    analyze_waveform_only,
    normalize_merge_window_ms,
    normalize_peak_sensitivity,
    normalize_valley_ratio,
    reanalyze_waveform_only,
    reanalyze_saved_audio,
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

            try:
                context["analysis_result"] = reanalyze_waveform_only(audio_preview_url)
                context["segment_result"] = analyze_sustained_vowel_segment(
                    audio_preview_url=audio_preview_url,
                    start_seconds=selection_start,
                    end_seconds=selection_end,
                )
            except Exception as exc:
                context["error_message"] = f"선택 구간 분석에 실패했습니다: {exc}"

            return render(request, "voice_analysis/sustained_vowel_analysis.html", context)

        uploaded_file = request.FILES.get("audio_file")

        if uploaded_file is None:
            context["error_message"] = "분석할 음성 파일을 선택해 주세요."
        else:
            try:
                context["analysis_result"] = analyze_waveform_only(uploaded_file)
            except Exception as exc:
                context["error_message"] = f"음성 분석에 실패했습니다: {exc}"

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

        if uploaded_file is None:
            context["error_message"] = "분석할 음성 파일을 선택해 주세요."
        else:
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

    return render(request, "voice_analysis/ddk_analysis.html", context)


def help_periodicity(request):
    return render(request, "voice_analysis/help_periodicity.html")