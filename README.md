# 🎙️ Voice Management System

Django 기반의 음성 데이터 관리 및 분석 시스템

[![Django](https://img.shields.io/badge/Django-4.2.24-green.svg)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.9-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [시스템 요구사항](#시스템-요구사항)
- [설치 방법](#설치-방법)
- [사용 방법](#사용-방법)
- [API 문서](#api-문서)
- [프로젝트 구조](#프로젝트-구조)
- [문서](#문서)
- [기여하기](#기여하기)

## 🎯 개요

Voice Management System은 음성 데이터를 체계적으로 수집, 관리, 분석하기 위한 웹 기반 플랫폼입니다. 
Whisper AI를 활용한 자동 전사, 음성 분석, 메타데이터 관리 등의 기능을 제공합니다.

### 주요 사용 사례
- 🧒 **아동 발화 데이터** 수집 및 분석
- 👴 **노인 발화 데이터** 수집 및 관리
- 🔊 **청각 장애** 관련 음성 데이터 연구
- 🗣️ **비정형 발화** 데이터 분석
- 📊 **음성 품질 분석** 및 SNR 측정

## ✨ 주요 기능

### 🎤 음성 데이터 관리
- **다중 포맷 지원**: WAV, M4A 등 다양한 오디오 포맷
- **카테고리별 분류**: 아동, 노인, 청각장애, 비정형, 정상
- **메타데이터 관리**: 성별, 나이, 생년월일, 고유 ID 등
- **파일 재업로드**: 기존 메타데이터 유지하면서 음성 파일만 교체

### 🤖 AI 전사 기능
- **Whisper 자동 전사**: OpenAI Whisper 모델을 활용한 한국어 음성 인식
- **수동 전사 편집**: 자동 전사 결과 수정 및 보정
- **이중 필드 시스템**: 
  - `transcript`: AI 자동 전사 원본 (읽기 전용)
  - `manual_transcript`: 사용자 수동 편집 (편집 가능)

### 📊 음성 분석
- **SNR (Signal-to-Noise Ratio) 측정**: 평균, 최대, 최소값
- **파형 시각화**: WaveSurfer.js 기반 대칭 dB 스케일 (+40 to -40)
- **재생 컨트롤**: 웹 기반 오디오 플레이어

### 🗺️ 위치 정보
- **Leaflet.js 지도**: OpenStreetMap 기반 무료 지도 서비스
- **사용자 프로필**: 위치 정보 표시 및 관리

### 🔍 검색 및 필터링
- **카테고리별 필터**: 5가지 카테고리로 분류
- **고유 ID 필터**: 동일 참가자의 모든 녹음 조회
- **전체 검색**: 다양한 필드 기반 검색

### 📱 API 지원
- **RESTful API**: React Native 모바일 앱 지원
- **JSON 응답**: 표준화된 데이터 형식
- **CORS 설정**: 크로스 도메인 요청 지원

## 🖥️ 시스템 요구사항

### 필수 요구사항
- Python 3.9+
- Django 4.2.24
- SQLite 3 (또는 PostgreSQL, MySQL)
- 최소 4GB RAM (Whisper 모델 로딩용)
- 최소 2GB 디스크 공간

### 권장 사양
- Python 3.9 이상
- 8GB RAM 이상
- CUDA 지원 GPU (Whisper 가속화용)
- SSD 스토리지

## 🚀 설치 방법

### 1. 저장소 클론

```bash
git clone https://github.com/exphon/voice_project.git
cd voice_project
```

### 2. 가상환경 생성 및 활성화

```bash
# Anaconda 사용 시
conda create -n voice_env python=3.9
conda activate voice_env

# venv 사용 시
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
.\venv\Scripts\activate  # Windows
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

`.env` 파일 생성:

```bash
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com
```

### 5. 데이터베이스 마이그레이션

```bash
python manage.py migrate
```

### 6. 관리자 계정 생성

```bash
python manage.py createsuperuser
```

### 7. 서버 실행

```bash
# 개발 서버
python manage.py runserver 0.0.0.0:8010

# 프로덕션 (nohup 사용)
nohup python manage.py runserver 0.0.0.0:8010 > django_server.log 2>&1 &
```

서버 접속: http://localhost:8010

## 📖 사용 방법

### 로그인 및 회원가입

1. **회원가입**: `/accounts/signup/`
   - 이메일 주소로 계정 생성
   - 자동 로그인 처리

2. **로그인**: `/accounts/login/`
   - 이메일과 비밀번호로 로그인

### 음성 파일 업로드

1. **대시보드 접속**: `/dashboard/`
2. **카테고리 선택**: 아동, 노인, 청각장애, 비정형, 정상 중 선택
3. **파일 업로드**: 
   - 오디오 파일 선택
   - 메타데이터 입력 (성별, 나이, 고유 ID 등)
   - 업로드 버튼 클릭

### Whisper 전사 실행

1. **상세 페이지 이동**: 음성 파일 클릭
2. **Whisper 전사 버튼 클릭**: 자동 전사 시작
3. **결과 확인**: `transcript` 필드에 자동 저장
4. **수동 편집**: 전사 수정 폼에서 내용 보정

### 전사 내용 편집

1. **전사 수정 탭 클릭**
2. `manual_transcript` 필드에서 내용 편집
3. **저장 버튼 클릭**
4. 자동 전사 원본(`transcript`)은 보존됨

### 고유 ID로 필터링

1. **상세 페이지**에서 고유 ID 클릭
2. 동일한 고유 ID를 가진 모든 녹음 조회
3. 테이블 형식으로 정렬된 목록 표시

## 🔌 API 문서

### 엔드포인트

#### 카테고리별 오디오 목록

```http
GET /api/audio/category/{category}/
```

**카테고리**: `child`, `senior`, `atypical`, `auditory`, `normal`

**응답**:
```json
{
  "category": "child",
  "count": 100,
  "results": [
    {
      "id": 1,
      "audio_file": "/media/audio/...",
      "transcript": "전사 내용",
      "auto_transcript": "원본 자동 전사",
      "manual_transcript": "수동 편집 전사",
      "gender": "남",
      "age": 5,
      "status": "completed",
      "snr_mean": 25.5,
      "created_at": "2025-01-27T10:00:00Z"
    }
  ]
}
```

#### 전체 오디오 목록

```http
GET /api/audio/all/
```

#### 오디오 상세 정보

```http
GET /api/audio/{id}/
```

#### 오디오 정보 수정

```http
PUT /api/audio/{id}/
PATCH /api/audio/{id}/
```

**요청 본문**:
```json
{
  "manual_transcript": "수정된 전사 내용",
  "gender": "남",
  "age": 6
}
```

### 인증

현재는 기본 Django 세션 인증을 사용합니다. API 키 인증은 향후 추가 예정입니다.

## 📁 프로젝트 구조

```
voice_project/
├── voice_app/                # 메인 애플리케이션
│   ├── models.py            # AudioRecord 모델
│   ├── views.py             # 뷰 함수들
│   ├── tasks.py             # Whisper 전사 작업
│   ├── whisper_utils.py     # Whisper 유틸리티
│   ├── audio_reupload.py    # 파일 재업로드 유틸리티
│   ├── urls.py              # URL 라우팅
│   ├── templates/           # HTML 템플릿
│   └── migrations/          # 데이터베이스 마이그레이션
├── accounts/                # 인증 애플리케이션
│   ├── views.py            # 로그인/회원가입
│   └── templates/          # 인증 템플릿
├── voice_project/          # 프로젝트 설정
│   ├── settings.py         # Django 설정
│   ├── urls.py             # 메인 URL 설정
│   └── wsgi.py             # WSGI 설정
├── media/                  # 업로드된 미디어 파일
├── assets/                 # 정적 자산
├── docs/                   # 문서 파일들
│   ├── API_ASSETS_GUIDE.md
│   ├── AUDIO_REUPLOAD_GUIDE.md
│   ├── GENDER_TRANSLATION_GUIDE.md
│   ├── METADATA_FIELDS_MAPPING.md
│   ├── TRANSCRIPT_FIELD_UPDATE_GUIDE.md
│   ├── WHISPER_TEST_GUIDE.md
│   └── WHISPER_TRANSCRIPTION_REVIEW.md
├── manage.py               # Django 관리 스크립트
├── requirements.txt        # Python 의존성
└── README.md              # 이 파일
```

## 📚 문서

자세한 문서는 다음 가이드를 참조하세요:

- [API 자산 가이드](docs/API_ASSETS_GUIDE.md)
- [오디오 재업로드 가이드](docs/AUDIO_REUPLOAD_GUIDE.md)
- [성별 번역 가이드](docs/GENDER_TRANSLATION_GUIDE.md)
- [메타데이터 필드 매핑](docs/METADATA_FIELDS_MAPPING.md)
- [전사 필드 업데이트 가이드](docs/TRANSCRIPT_FIELD_UPDATE_GUIDE.md)
- [Whisper 테스트 가이드](docs/WHISPER_TEST_GUIDE.md)
- [Whisper 전사 검토](docs/WHISPER_TRANSCRIPTION_REVIEW.md)

## 🔧 주요 기술 스택

### Backend
- **Django 4.2.24**: 웹 프레임워크
- **Django REST Framework**: API 개발
- **SQLite/PostgreSQL**: 데이터베이스
- **Whisper (OpenAI)**: 음성 인식
- **librosa**: 오디오 분석

### Frontend
- **Bootstrap 5.1.3**: UI 프레임워크
- **WaveSurfer.js 6.6.4**: 파형 시각화
- **Leaflet.js 1.9.4**: 지도 서비스
- **Font Awesome 6.0.0**: 아이콘

### AI/ML
- **Whisper Base Model**: 한국어 음성 인식
- **WhisperX (Optional)**: 고급 정렬 기능

## 🗄️ 데이터베이스 스키마

### AudioRecord 모델

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | Integer | 기본 키 |
| `audio_file` | FileField | 오디오 파일 |
| `category` | CharField | 카테고리 (child/senior/atypical/auditory/normal) |
| `gender` | CharField | 성별 (남/여) |
| `age` | Integer | 나이 |
| `age_in_months` | Integer | 개월 수 (아동용) |
| `birth_date` | DateField | 생년월일 |
| `identifier` | CharField | 고유 ID (참가자 식별) |
| `transcript` | TextField | AI 자동 전사 (읽기 전용) |
| `manual_transcript` | TextField | 사용자 수동 전사 (편집 가능) |
| `status` | CharField | 처리 상태 (pending/processing/completed/failed) |
| `snr_mean` | Float | 평균 SNR |
| `snr_max` | Float | 최대 SNR |
| `snr_min` | Float | 최소 SNR |
| `category_specific_data` | JSONField | 카테고리별 메타데이터 |
| `alignment_data` | JSONField | WhisperX 정렬 데이터 |
| `created_at` | DateTime | 생성 시간 |
| `updated_at` | DateTime | 수정 시간 |

## 🔄 마이그레이션 히스토리

- **0011**: `identifier` 필드 추가
- **0012**: `age_in_months`, `birth_date` 필드 추가
- **0013**: `manual_transcription` 필드 추가
- **0014**: 필드명 변경 (`transcription` → `transcript`)
- **0015**: 데이터 마이그레이션 (982개 레코드 업데이트)

## 🎨 UI 특징

### 대시보드
- 카테고리별 통계 카드
- 최근 업로드 파일 목록
- 빠른 업로드 버튼

### 오디오 상세 페이지
- 메타데이터 5열 그리드 레이아웃
- WaveSurfer.js 파형 시각화 (대칭 dB 스케일)
- 재생/일시정지 컨트롤
- 탭 기반 편집 인터페이스
  - 전사 수정
  - 메타데이터 수정
  - 카테고리 정보 수정

### 목록 페이지
- 정렬 가능한 테이블 헤더
- 상태 뱃지 (대기/처리중/완료/실패)
- 인라인 오디오 플레이어
- 페이지네이션

## 🔐 보안 기능

- CSRF 보호
- SQL Injection 방지 (Django ORM)
- XSS 방지 (템플릿 이스케이핑)
- 파일 업로드 검증
- 사용자 인증 및 권한 관리

## 🚧 알려진 제한사항

1. **WhisperX**: 선택적 의존성으로, 설치되지 않은 경우 기본 Whisper만 사용
2. **대용량 파일**: 매우 큰 오디오 파일은 메모리 제한으로 처리 실패 가능
3. **동시 전사**: 현재는 순차 처리, 대규모 배치 작업 시 Celery 권장
4. **GPU 가속**: CUDA 설정 필요, CPU만으로도 작동하지만 느림

## 🛣️ 로드맵

### v1.1 (예정)
- [ ] Celery를 통한 비동기 작업 처리
- [ ] 배치 전사 기능
- [ ] 전사 히스토리 추적
- [ ] API 키 인증

### v1.2 (예정)
- [ ] PostgreSQL 지원
- [ ] Docker 컨테이너화
- [ ] 고급 검색 필터
- [ ] 데이터 내보내기 (CSV, JSON)

### v2.0 (장기)
- [ ] 실시간 음성 전사
- [ ] 화자 분리 (Speaker Diarization)
- [ ] 다국어 지원
- [ ] 클라우드 스토리지 통합

## 🤝 기여하기

기여를 환영합니다! 다음 단계를 따라주세요:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### 코드 스타일
- PEP 8 준수
- 함수와 클래스에 docstring 작성
- 의미 있는 커밋 메시지

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 👥 개발팀

- **Project Owner**: exphon
- **Contributors**: [기여자 목록](https://github.com/exphon/voice_project/graphs/contributors)

## 📞 문의

- **GitHub Issues**: [이슈 생성](https://github.com/exphon/voice_project/issues)
- **Email**: your-email@example.com

## 🙏 감사의 말

- [OpenAI Whisper](https://github.com/openai/whisper) - 훌륭한 음성 인식 모델
- [Django](https://www.djangoproject.com/) - 강력한 웹 프레임워크
- [WaveSurfer.js](https://wavesurfer-js.org/) - 오디오 시각화 라이브러리
- [Leaflet](https://leafletjs.com/) - 오픈소스 지도 라이브러리

---

**Made with ❤️ by exphon**

*Last Updated: 2025-01-27*
