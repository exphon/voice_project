# accounts/views.py
from django.contrib.auth.views import PasswordChangeView, LoginView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.shortcuts import redirect
from .forms import CustomUserCreationForm
from django.contrib.auth.forms import PasswordChangeForm


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('voice_app:index')
    
    def form_invalid(self, form):
        messages.error(self.request, '사용자명 또는 비밀번호가 올바르지 않습니다.')
        return super().form_invalid(form)


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f'{form.cleaned_data["username"]}님, 회원가입이 완료되었습니다. '
            f'관리자 승인 후 데이터 수정 권한을 부여받을 수 있습니다. '
            f'로그인하여 서비스를 이용하세요.'
        )
        return response


@method_decorator(login_required, name='dispatch')
class CustomPasswordChangeView(PasswordChangeView):
    form_class = PasswordChangeForm
    template_name = 'registration/password_change.html'
    success_url = reverse_lazy('password_change_done')