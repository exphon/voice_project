from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static  
from django.http import JsonResponse

# voice_app의 index 뷰를 import
from voice_app.views import index

# 기본 API 뷰 (테스트용)
def api_test(request):
    return JsonResponse({
        'message': 'Django CORS 설정이 성공적으로 적용되었습니다!',
        'status': 'success'
    })

urlpatterns = [
    path('', index, name='index'),  # voice_app의 index 뷰 사용
    path('admin/', admin.site.urls),
    path('api/test/', api_test, name='api_test'),  # 테스트용 API 엔드포인트
    # API / Web URLConf 분리 (namespace 중복 경고(W005) 방지)
    path('api/', include(('voice_app.urls_api', 'voice_app_api'), namespace='voice_app_api')),
    # legacy alias: 일부 클라이언트/스크립트에서 /audio/ 경로를 사용할 수 있어 API로 연결
    path('audio/', include(('voice_app.urls_api', 'voice_app_api'), namespace='voice_app_audio')),
    # Web UI는 /voice/ 아래로 고정
    path('voice/', include(('voice_app.urls_web', 'voice_app'), namespace='voice_app')),
    path('accounts/', include('accounts.urls')),  # accounts 앱 URL 추가
]

# 미디어 파일 URL 패턴 추가 (개발 환경)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Assets 파일 URL 패턴 추가 (오디오 문제 파일 등)
    urlpatterns += static(settings.ASSETS_URL, document_root=settings.ASSETS_ROOT)
