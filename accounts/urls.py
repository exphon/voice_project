# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView, TemplateView

from .views import SignUpView, CustomPasswordChangeView

app_name = 'accounts'  # namespace 추가

urlpatterns = [
    path("", RedirectView.as_view(url='/'), name="accounts_home"),  # /accounts/를 홈으로 리다이렉트
    path("login/", auth_views.LoginView.as_view(template_name='registration/login.html'), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page='/'), name="logout"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("password_change/", CustomPasswordChangeView.as_view(), name="password_change"),
    path("password_change/done/", TemplateView.as_view(template_name="registration/password_change_done.html"), name="password_change_done"),
]