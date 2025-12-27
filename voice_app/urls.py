"""Deprecated URLConf wrapper.

이 파일은 과거에 Web UI + API URL을 한 곳에 섞어 관리하던 레거시 URLConf 입니다.
현재는 다음 두 파일로 분리되어 있습니다.

- Web UI: voice_app/urls_web.py  (프로젝트에서는 /voice/ 로 include)
- API:    voice_app/urls_api.py  (프로젝트에서는 /api/ 로 include)

이 파일은 **하위 호환성**을 위해서만 유지되며, 신규 개발에서는 사용하지 마세요.
"""

import warnings

from django.urls import include, path


warnings.warn(
    "voice_app.urls is deprecated. Use voice_app.urls_web and voice_app.urls_api.",
    DeprecationWarning,
    stacklevel=2,
)


urlpatterns = [
    path('', include('voice_app.urls_web')),
    path('', include('voice_app.urls_api')),
]
