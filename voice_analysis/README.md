# voice_analysis

Django 앱으로, 업로드된 음성 파일에 대한 다양한 음성 분석 기능을 제공합니다.

---

## 주요 분석 기능

### 1. DDK (Diadochokinesis) 분석 — `/ddk/`

반복 음절(퍼터커) 발화 속도 및 규칙성을 측정하는 분석입니다.

- **파형 + 진폭 엔벨로프 추출**: librosa로 파형을 로드하고, Hilbert 변환으로 진폭 엔벨로프를 계산합니다.
- **음절 피크 감지**: `scipy.signal.find_peaks`로 엔벨로프 상의 피크를 검출하고, 인접 피크를 병합하여 음절 수를 계산합니다.
- **파라미터 조정 (민감도 슬라이더)**:
  - `peak_sensitivity` (0.05 ~ 1.0, 기본값 **0.8**): 피크 높이 임계값 및 최소 간격 제어
  - `merge_window_ms` (40 ~ 240 ms, 기본값 120): 인접 피크 병합 윈도우
  - `valley_ratio` (0.30 ~ 0.95, 기본값 0.58): 피크 간 골(valley) 깊이 비율 기준
- **Whisper 전사(선택)**: 음성을 전사한 뒤, 한글 초성을 P/T/K 계열로 분류하여 `퍼`, `터`, `커`, `퍼터커` 토큰으로 정규화합니다.
- **재전사**: 업로드 없이 저장된 프리뷰 파일에 파라미터를 바꿔 재분석할 수 있습니다.
- **분석 저장**: 분석 결과(Envelope Peak 개수, Peak 민감도, 병합 창, Valley 비율)를 `VoiceAnalysis` DB에 저장합니다.
  - 파일명으로 `AudioRecord`를 매칭하여 저장 대상 화자·음성 정보를 확인합니다.
  - 이미 저장된 이력이 있으면 confirm 대화상자를 통해 덮어쓸지 여부를 확인하고, 승인 시 기존 레코드를 UPDATE합니다.

**관련 함수 (`services.py`)**

| 함수 | 설명 |
|---|---|
| `analyze_waveform_envelope()` | 업로드 파일로부터 파형·엔벨로프·피크 분석 수행 |
| `analyze_waveform_envelope_from_url()` | 저장된 프리뷰 URL 기반 분석 |
| `reanalyze_saved_audio()` | 파라미터 변경 후 저장 파일 재분석 |
| `_merge_nearby_peaks()` | 인접 피크 병합 로직 |
| `constrain_whisper_transcript()` | 전사 결과를 퍼/터/커 토큰으로 정규화 |
| `constrain_transcript_token_count()` | 피크 수에 맞게 토큰 수 조정 |
| `summarize_repetition_tokens()` | 퍼/터/커/퍼터커 토큰 빈도 집계 |

**관련 뷰 (`views.py`)**

| 뷰 | 설명 |
|---|---|
| `save_ddk_analysis()` | DDK 분석 결과를 DB에 저장 또는 덮어쓰기 (POST, JSON) |

---

### 2. 지속 모음 분석 — `/sustained-vowel/`

"아~" 같은 지속 발화 구간을 분석하여 발성 품질 지표를 측정합니다.

- **파형 시각화**: 파일 업로드 시 파형을 표시하고, 사용자가 분석 구간(시작/종료 초)을 직접 선택합니다.
- **선택 구간 상세 분석** (Parselmouth/Praat 기반):

  | 지표 | 설명 |
  |---|---|
  | F1, F2 (포먼트) | Burg 알고리즘으로 구간 중앙 지점의 포먼트 주파수 추출 |
  | Jitter (local) | 기본 주기 변동률, 성대 진동 안정성 평가 |
  | Shimmer (local) | 진폭 변동률, 음성 강도 안정성 평가 |
  | HNR (dB) | 조화 잡음비 (Harmonics-to-Noise Ratio) |
  | CPP (Cepstral Peak Prominence) | Praat `To PowerCepstrogram` 기반 스펙트럼 주기성 지표 |

- **켑스트럼 프로파일**: 직접 구현한 FFT 기반 파워 켑스트럼으로 퀘프렌시~크기(dB) 곡선과 회귀선, CPP 돌출량을 반환합니다.

**관련 함수 (`services.py`)**

| 함수 | 설명 |
|---|---|
| `analyze_waveform_only()` | 업로드 파일의 파형만 추출 (구간 선택 전 초기 표시용) |
| `reanalyze_waveform_only()` | 저장된 프리뷰 URL로 파형 재로드 |
| `analyze_sustained_vowel_segment()` | 선택 구간에 대한 포먼트/지터/쉬머/HNR/CPP 계산 |
| `_compute_cepstral_profile()` | FFT 기반 파워 켑스트럼 및 CPP 돌출량 계산 |

---

### 3. 기본 레코드 분석 (내부 API)

`AudioRecord` 모델과 연동하여 DB에 분석 결과를 저장하는 배치성 분석입니다.

- `VoiceAnalysis` 모델에 분석 유형·상태·결과 JSON·오류 메시지를 기록합니다.
- 분석 유형: `basic` / `snr` / `alignment` / `diarization` / `ddk` / `custom`
- 분석 상태: `pending` → `processing` → `completed` / `failed`

**관련 함수 (`services.py`)**

| 함수 | 설명 |
|---|---|
| `analyze_audio_record()` | AudioRecord에 대한 분석 실행 및 VoiceAnalysis 레코드 생성 |
| `build_basic_analysis_payload()` | SNR·전사·메타데이터 요약 딕셔너리 생성 |
| `build_analysis_summary()` | 결과 딕셔너리로부터 요약 문자열 생성 |

---

## 유틸리티

| 함수 | 설명 |
|---|---|
| `_downsample_series()` | 시각화용 시계열 다운샘플링 (최대 4,000 포인트) |
| `_normalize_series()` | 파형·엔벨로프 peak 정규화 |
| `resolve_preview_audio_path()` | 미디어 URL → 파일 시스템 경로 변환 (path traversal 방어 포함) |
| `_match_audio_record_by_filename()` | 파일명·identifier 패턴으로 AudioRecord 매칭 |
| `_build_speaker_info()` | AudioRecord로부터 화자 정보 딕셔너리 생성 |
| `_save_preview_audio()` | 임시 파일을 미디어 디렉터리에 UUID 이름으로 저장 |

---

## 모델 (`models.py`)

### `VoiceAnalysis`

`AudioRecord`와 1:N 관계로, 분석 요청 1건을 표현합니다.

| 필드 | 설명 |
|---|---|
| `analysis_type` | 분석 유형 (basic / snr / alignment / diarization / **ddk** / custom) |
| `status` | 처리 상태 (pending / processing / completed / failed) |
| `input_snapshot` | 분석 시점의 입력 상태 스냅샷 (JSON) |
| `result_data` | 분석 결과 (JSON) |
| `summary` | 결과 요약 텍스트 |
| `error_message` | 실패 시 오류 메시지 |
| `started_at` / `completed_at` | 처리 시작·완료 시각 |

---

## URL 구조

| URL | 뷰 | 설명 |
|---|---|---|
| `/voice-analysis/` | `index` | 분석 메뉴 인덱스 |
| `/voice-analysis/sustained-vowel/` | `sustained_vowel_analysis` | 지속 모음 분석 |
| `/voice-analysis/ddk/` | `ddk_analysis` | DDK 반복 음절 분석 |
| `/voice-analysis/ddk/save/` | `save_ddk_analysis` | DDK 분석 결과 저장 (POST, JSON) |
| `/voice-analysis/help/periodicity/` | `help_periodicity` | 주기성 지표 도움말 |

---

## 의존 라이브러리

| 라이브러리 | 용도 |
|---|---|
| `librosa` | 음성 파일 로드, 샘플레이트 처리 |
| `numpy` | 배열 연산, FFT, 켑스트럼 계산 |
| `scipy.signal` | Hilbert 변환 (엔벨로프), 피크 검출 |
| `parselmouth` (Praat) | 포먼트, 지터, 쉬머, HNR, CPP 계산 |
