# 🚀 인증 시스템 빠른 시작 가이드

## 1단계: 권한 그룹 설정

```bash
cd /var/www/html/dj_voice_manage
python3 manage.py setup_permissions
```

**출력 예시:**
```
✓ Viewer 그룹 생성됨
  - Viewer 권한: 데이터 조회만 가능
✓ Editor 그룹 생성됨
  - Editor 권한: 데이터 추가/수정/삭제/조회 가능

권한 설정 완료!
```

---

## 2단계: 데이터베이스 마이그레이션

```bash
python3 manage.py migrate
```

---

## 3단계: 슈퍼유저 생성 (선택사항)

```bash
python3 manage.py createsuperuser
```

---

## 4단계: 개발 서버 테스트

```bash
./run_dev.sh
```

브라우저에서 확인:
- 회원가입: `http://210.125.93.241:8011/accounts/signup/`
- 로그인: `http://210.125.93.241:8011/accounts/login/`
- 관리자: `http://210.125.93.241:8011/admin/`

---

## 5단계: 사용자 권한 관리

### 방법 1: Django Admin 사용 (권장)

1. `http://210.125.93.241:8011/admin/` 접속
2. **Users** → 사용자 선택
3. **Groups** 섹션:
   - `Editor` 체크 → 수정 권한 부여
   - `Viewer`만 체크 → 조회만 가능
4. 저장

### 방법 2: 커맨드로 관리

```bash
python3 manage.py shell

>>> from django.contrib.auth.models import User, Group
>>> user = User.objects.get(username='사용자명')
>>> editor = Group.objects.get(name='Editor')
>>> user.groups.add(editor)  # Editor 권한 부여
>>> exit()
```

---

## 테스트 시나리오

### 1. 신규 사용자 가입 테스트

1. `/accounts/signup/` 접속
2. 회원가입 완료
3. 로그인 → **자동으로 Viewer 권한** 부여됨
4. 데이터 조회만 가능, 수정/삭제 불가

### 2. Editor 권한 부여 테스트

1. Admin에서 사용자를 Editor 그룹에 추가
2. 로그아웃 후 재로그인
3. **데이터 수정/삭제 가능**

---

## 코드 예시: Views에 권한 적용

### Function-Based View

```python
# voice_app/views.py
from accounts.decorators import editor_required

@editor_required
def delete_audio(request, pk):
    audio = AudioRecord.objects.get(pk=pk)
    audio.delete()
    return redirect('voice_app:index')
```

### Class-Based View

```python
# voice_app/views.py
from accounts.mixins import EditorRequiredMixin
from django.views.generic import UpdateView

class AudioUpdateView(EditorRequiredMixin, UpdateView):
    model = AudioRecord
    fields = ['transcription', 'status']
    template_name = 'audio_update.html'
```

---

## 배포 (프로덕션 적용)

```bash
# develop 브랜치에서 작업 완료 후
./deploy.sh
```

deploy.sh가 자동으로:
1. main 브랜치로 병합
2. 데이터베이스 마이그레이션 실행
3. 프로덕션 서버 재시작 (port 8010)

---

## URL 구조

| URL | 설명 | 권한 |
|-----|------|------|
| `/accounts/signup/` | 회원가입 | 누구나 |
| `/accounts/login/` | 로그인 | 누구나 |
| `/accounts/logout/` | 로그아웃 | 로그인 필요 |
| `/admin/` | 관리자 페이지 | 슈퍼유저 |

---

## 문제 해결

### Q: 권한 그룹이 없다고 나옴
```bash
python3 manage.py setup_permissions
```

### Q: 기존 사용자에게 권한 부여
```bash
python3 manage.py shell

>>> from django.contrib.auth.models import User, Group
>>> viewer = Group.objects.get(name='Viewer')
>>> for user in User.objects.all():
>>>     if not user.groups.exists():
>>>         user.groups.add(viewer)
>>> exit()
```

### Q: 사용자 권한 확인
```bash
python3 manage.py shell

>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='사용자명')
>>> print(user.groups.all())
>>> exit()
```

---

## 다음 단계

✅ 권한 시스템 설정 완료  
✅ 로그인/회원가입 페이지 구현  
✅ 2단계 권한 체계 (Viewer/Editor)  

**TODO:**
- [ ] 기존 views에 권한 데코레이터 적용
- [ ] 템플릿에 권한별 UI 분기 추가
- [ ] API 엔드포인트에 권한 체크 추가

상세 가이드: `AUTH_PERMISSIONS_GUIDE.md` 참고
