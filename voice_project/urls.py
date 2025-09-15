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
    path('api/', include('voice_app.urls')),  # api/ 경로를 voice_app으로 연결
    path('voice/', include('voice_app.urls')),  # voice_app URLs 포함
]

# 미디어 파일 URL 패턴 추가
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
