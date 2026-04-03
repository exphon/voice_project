import os

from django.conf import settings
from django.core.cache import cache


def _get_audio_folder_size_bytes(audio_root: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(audio_root):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                total += os.path.getsize(file_path)
            except (FileNotFoundError, PermissionError, OSError):
                continue
    return total


def audio_download_size(request):
    """Adds `audio_download_size_mb` to all templates.

    Uses a short cache to avoid expensive os.walk on every request.
    """
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        return {
            'audio_download_size_mb': None,
        }

    allowed_staff_ids = getattr(settings, 'DOWNLOAD_SIZE_STAFF_USER_IDS', []) or []
    can_view_size = bool(getattr(user, 'is_superuser', False)) or (
        bool(getattr(user, 'is_staff', False)) and getattr(user, 'id', None) in allowed_staff_ids
    )

    if not can_view_size:
        return {
            'audio_download_size_mb': None,
        }

    audio_root = os.path.join(settings.MEDIA_ROOT, 'audio')
    if not os.path.isdir(audio_root):
        return {
            'audio_download_size_mb': None,
        }

    cache_key = 'audio_folder_size_bytes_v1'
    size_bytes = cache.get(cache_key)
    if size_bytes is None:
        size_bytes = _get_audio_folder_size_bytes(audio_root)
        cache.set(cache_key, size_bytes, timeout=300)  # 5 minutes

    size_mb = size_bytes / (1024 * 1024)
    return {
        'audio_download_size_mb': round(size_mb, 1),
    }
