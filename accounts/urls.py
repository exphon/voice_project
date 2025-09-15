# accounts/urls.py
from django.urls import path
from django.views.generic import RedirectView, TemplateView

from .views import SignUpView, CustomPasswordChangeView


urlpatterns = [
    path("", RedirectView.as_view(url='/'), name="accounts_home"),  # /accounts/를 홈으로 리다이렉트
    path("signup/", SignUpView.as_view(), name="signup"),
    path("password_change/", CustomPasswordChangeView.as_view(), name="password_change"),
    path("password_change/done/", TemplateView.as_view(template_name="registration/password_change_done.html"), name="password_change_done"),
]