# accounts/mixins.py
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.shortcuts import redirect


class GroupRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """특정 그룹에 속한 사용자만 접근 가능한 Mixin"""
    group_required = None
    
    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.group_required is None:
            return True
        if isinstance(self.group_required, str):
            return self.request.user.groups.filter(name=self.group_required).exists()
        return self.request.user.groups.filter(name__in=self.group_required).exists()
    
    def handle_no_permission(self):
        messages.error(self.request, '이 작업을 수행할 권한이 없습니다.')
        return redirect('voice_app:index')


class EditorRequiredMixin(GroupRequiredMixin):
    """Editor 그룹 사용자만 접근 가능"""
    group_required = 'Editor'


class ViewerRequiredMixin(GroupRequiredMixin):
    """Viewer 또는 Editor 그룹 사용자만 접근 가능"""
    group_required = ['Viewer', 'Editor']
