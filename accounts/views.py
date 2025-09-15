# accounts/views.py
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


class SignUpView(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"


@method_decorator(login_required, name='dispatch')
class CustomPasswordChangeView(PasswordChangeView):
    form_class = PasswordChangeForm
    template_name = 'registration/password_change.html'
    success_url = reverse_lazy('password_change_done')