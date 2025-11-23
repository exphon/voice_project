# 인증 및 권한 시스템 사용 가이드

## 시스템 개요

DJ Voice Manage는 2단계 권한 시스템을 사용합니다:

### 1. **Viewer (조회자)** - 기본 권한
- 데이터 조회만 가능
- 신규 가입 시 자동으로 부여
- 수정/삭제 불가

### 2. **Editor (편집자)** - 수정 권한
- 데이터 조회, 추가, 수정, 삭제 가능
- 관리자가 수동으로 부여
- 데이터 관리 전체 권한

---

## 초기 설정

### 1. 권한 그룹 생성

```bash
cd /var/www/html/dj_voice_manage
python3 manage.py setup_permissions
```

이 명령어는 다음을 수행합니다:
- `Viewer` 그룹 생성 (읽기 전용)
- `Editor` 그룹 생성 (전체 권한)
- 각 그룹에 적절한 권한 할당

### 2. 첫 사용자 생성 (선택사항)

```bash
python3 manage.py createsuperuser
```

---

## 사용자 관리

### 신규 사용자 가입 프로세스

1. **사용자가 회원가입** (`/accounts/signup/`)
   - 기본 정보 입력 (사용자명, 이메일, 이름, 비밀번호)
   - 자동으로 `Viewer` 그룹에 추가됨

2. **관리자가 권한 승격** (필요 시)
   - Django Admin 페이지 접속: `http://210.125.93.241:8010/admin/`
   - Users → 해당 사용자 선택
   - Groups에서 `Editor` 추가
   - 저장

---

## 코드에서 권한 사용하기

### 1. Function-Based Views (FBV)

```python
from accounts.decorators import editor_required, viewer_required

# Editor만 접근 가능
@editor_required
def edit_record(request, pk):
    record = AudioRecord.objects.get(pk=pk)
    # 수정 로직...
    return render(request, 'edit.html', {'record': record})

# Viewer 이상 접근 가능 (Viewer + Editor)
@viewer_required
def view_record(request, pk):
    record = AudioRecord.objects.get(pk=pk)
    return render(request, 'view.html', {'record': record})
```

### 2. Class-Based Views (CBV)

```python
from accounts.mixins import EditorRequiredMixin, ViewerRequiredMixin
from django.views.generic import UpdateView, DetailView

# Editor만 접근 가능
class AudioRecordUpdateView(EditorRequiredMixin, UpdateView):
    model = AudioRecord
    fields = ['transcription', 'status']
    template_name = 'audio_update.html'

# Viewer 이상 접근 가능
class AudioRecordDetailView(ViewerRequiredMixin, DetailView):
    model = AudioRecord
    template_name = 'audio_detail.html'
```

### 3. 템플릿에서 권한 체크

```django
{% if user.groups.all.0.name == 'Editor' or user.is_superuser %}
    <a href="{% url 'edit_record' record.id %}" class="btn btn-primary">수정</a>
    <button class="btn btn-danger" onclick="deleteRecord()">삭제</button>
{% else %}
    <p class="text-muted">수정 권한이 없습니다.</p>
{% endif %}
```

또는:

```django
{% load auth_extras %}

{% if user|has_group:"Editor" %}
    <!-- 수정 버튼 표시 -->
{% endif %}
```

### 4. 커스텀 템플릿 태그 (선택사항)

`accounts/templatetags/auth_extras.py` 생성:

```python
from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists()

@register.filter(name='is_editor')
def is_editor(user):
    return user.groups.filter(name='Editor').exists() or user.is_superuser

@register.filter(name='is_viewer')
def is_viewer(user):
    return user.groups.filter(name__in=['Viewer', 'Editor']).exists()
```

---

## API 권한 (REST Framework)

`voice_app/views_2.py` 등에서 API 권한 설정:

```python
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_audio(request):
    # Editor 권한 체크
    if not request.user.groups.filter(name='Editor').exists() and not request.user.is_superuser:
        return Response(
            {'error': '데이터 업로드 권한이 없습니다.'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    # 업로드 로직...
```

---

## 사용자 권한 변경 (관리자용)

### Django Admin에서 변경

1. `http://210.125.93.241:8010/admin/` 접속
2. **Users** 클릭
3. 변경할 사용자 선택
4. **Groups** 섹션에서:
   - Viewer → Editor로 승격: `Editor` 추가
   - Editor → Viewer로 강등: `Editor` 제거
5. **저장**

### 코드로 변경

```python
from django.contrib.auth.models import User, Group

user = User.objects.get(username='username')
editor_group = Group.objects.get(name='Editor')
viewer_group = Group.objects.get(name='Viewer')

# Editor로 승격
user.groups.add(editor_group)

# Viewer로 강등
user.groups.remove(editor_group)
user.groups.add(viewer_group)
```

---

## 보안 고려사항

1. **Superuser는 모든 권한 보유**
   - 관리자 계정은 신중하게 관리
   - `is_superuser=True`는 모든 권한 체크 우회

2. **기본값은 최소 권한**
   - 신규 사용자는 Viewer로 시작
   - 필요한 경우에만 Editor로 승격

3. **로그인 필수**
   - 모든 데이터 접근은 로그인 필요
   - `@login_required` 또는 `LoginRequiredMixin` 사용

4. **권한 체크 위치**
   - View 레벨에서 권한 체크
   - Template에서 UI 숨김은 보안이 아님 (추가 편의 기능)
   - API는 별도 권한 체크 필수

---

## URL 구조

```
/accounts/login/           - 로그인
/accounts/signup/          - 회원가입
/accounts/logout/          - 로그아웃
/accounts/password_change/ - 비밀번호 변경
/admin/                    - 관리자 페이지 (권한 관리)
```

---

## 테스트

### 권한 테스트 예시

```python
from django.test import TestCase
from django.contrib.auth.models import User, Group

class PermissionTestCase(TestCase):
    def setUp(self):
        # 그룹 생성
        self.viewer_group = Group.objects.create(name='Viewer')
        self.editor_group = Group.objects.create(name='Editor')
        
        # 사용자 생성
        self.viewer_user = User.objects.create_user('viewer', password='test123')
        self.viewer_user.groups.add(self.viewer_group)
        
        self.editor_user = User.objects.create_user('editor', password='test123')
        self.editor_user.groups.add(self.editor_group)
    
    def test_viewer_cannot_edit(self):
        self.client.login(username='viewer', password='test123')
        response = self.client.get('/edit/1/')
        self.assertEqual(response.status_code, 403)
    
    def test_editor_can_edit(self):
        self.client.login(username='editor', password='test123')
        response = self.client.get('/edit/1/')
        self.assertEqual(response.status_code, 200)
```

---

## 문제 해결

### 사용자가 로그인했는데 권한이 없다고 나옴

```bash
# 권한 그룹이 제대로 설정되었는지 확인
python3 manage.py shell
>>> from django.contrib.auth.models import User, Group
>>> user = User.objects.get(username='사용자명')
>>> user.groups.all()
>>> # 결과가 비어있으면 그룹 추가 필요
```

### 권한 그룹이 없음

```bash
python3 manage.py setup_permissions
```

### 모든 사용자에게 권한 부여하고 싶음

```python
# 모든 기존 사용자를 Viewer로 설정
from django.contrib.auth.models import User, Group

viewer_group = Group.objects.get(name='Viewer')
for user in User.objects.all():
    if not user.groups.exists():
        user.groups.add(viewer_group)
```
