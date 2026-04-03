# accounts/urls.py
from django.urls import path
from django.views.generic import RedirectView, TemplateView
from django.contrib.auth.views import LogoutView

from .views import SignUpView, CustomPasswordChangeView, CustomLoginView

app_name = 'accounts'  # namespace 추가

urlpatterns = [
    path("", RedirectView.as_view(url='/'), name="accounts_home"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page='/accounts/login/'), name="logout"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("password_change/", CustomPasswordChangeView.as_view(), name="password_change"),
    path("password_change/done/", TemplateView.as_view(template_name="registration/password_change_done.html"), name="password_change_done"),
]