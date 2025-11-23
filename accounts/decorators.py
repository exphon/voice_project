# accounts/decorators.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import redirect
from functools import wraps


def group_required(*group_names):
    """특정 그룹에 속한 사용자만 접근 가능"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.groups.filter(name__in=group_names).exists() or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, '이 작업을 수행할 권한이 없습니다.')
                return redirect('voice_app:index')
        return wrapper
    return decorator


def editor_required(view_func):
    """Editor 그룹 또는 superuser만 접근 가능"""
    return group_required('Editor')(view_func)


def viewer_required(view_func):
    """Viewer 또는 Editor 그룹 사용자만 접근 가능"""
    return group_required('Viewer', 'Editor')(view_func)
