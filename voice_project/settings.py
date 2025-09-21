import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-i_wrmes6gq8gxhy!*5h#96(1qfz=0cz^$ullvo@2$k9yqe5p6b"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['210.125.93.241', '0.0.0.0', 'localhost', 'tyoon.net']


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",    
    "corsheaders",         
    "voice_app",  # 음성 앱 활성화
    "accounts",  # 사용자 인증 앱
    # 'django_extensions',  # Django 확장 (필요시 주석 해제)
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # CORS 미들웨어를 맨 위에 추가
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "voice_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "voice_project.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ✅ 여기에 추가하세요
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# 새로운 assets 설정 추가
ASSETS_URL = '/assets/'
ASSETS_ROOT = BASE_DIR / 'assets'

# 로그인/로그아웃 리다이렉트 설정
LOGIN_REDIRECT_URL = '/'  # 로그인 후 음성 데이터 목록으로 리다이렉트
LOGOUT_REDIRECT_URL = '/'  # 로그아웃 후 홈페이지로 리다이렉트

# Django REST Framework 설정
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
}

# WhisperX 설정
WHISPERX_CONFIG = {
    'MODEL_SIZE': 'medium',  # tiny, base, small, medium, large, large-v2, large-v3
    'DEVICE': 'auto',  # 'auto', 'cpu', 'cuda'
    'COMPUTE_TYPE': 'auto',  # 'auto', 'int8', 'float16', 'float32'
    'BATCH_SIZE': 16,
    'TEMPERATURE': 0.0,
    'WORD_TIMESTAMPS': True,
    'SUPPORTED_LANGUAGES': [
        'en', 'ko', 'ja', 'zh', 'es', 'fr', 'de', 'it', 'pt', 'ru',
        'ar', 'tr', 'pl', 'ca', 'nl', 'sv', 'no', 'da', 'fi', 'hu'
    ]
}

# 파일 업로드 설정 (WhisperX용)
MAX_AUDIO_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_AUDIO_FORMATS = ['.wav', '.mp3', '.m4a', '.flac', '.mp4', '.webm', '.ogg']

# CORS 설정 (API 사용을 위해)
CORS_ALLOW_ALL_ORIGINS = True  # 개발용
CORS_ALLOW_CREDENTIALS = True  # 인증 정보 허용
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000", 
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8081",      # Expo 개발 서버
    "http://127.0.0.1:8081",      # Expo 개발 서버
    "http://10.52.193.109:8081",  # React Native 앱 요청 추가
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CSRF_TRUSTED_ORIGINS = [
    'http://210.125.93.241:8001',
    'http://210.125.93.214'
]

# HTTPS 설정 (nginx 프록시 사용 시)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_TLS = True

# 파일 업로드 크기 제한 설정 (React Native 음성 파일 업로드를 위해)
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB

# React Native 앱을 위한 추가 설정
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = False

# CSRF 예외 경로 설정 (API 업로드 경로)
CSRF_EXEMPT_URLS = [
    r'^/api/.*upload/$',
]

