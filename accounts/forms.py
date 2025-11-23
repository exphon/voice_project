# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='이메일')
    first_name = forms.CharField(max_length=30, required=True, label='이름')
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'password1', 'password2')
        labels = {
            'username': '사용자명',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 한글 help text
        self.fields['username'].help_text = '150자 이하. 영문, 숫자, @/./+/-/_ 만 가능합니다.'
        self.fields['password1'].help_text = '''
            <ul>
                <li>다른 개인 정보와 유사하지 않아야 합니다.</li>
                <li>최소 8자 이상이어야 합니다.</li>
                <li>일반적으로 사용되는 비밀번호는 사용할 수 없습니다.</li>
                <li>숫자로만 구성될 수 없습니다.</li>
            </ul>
        '''
        self.fields['password2'].help_text = '확인을 위해 이전과 동일한 비밀번호를 입력하세요.'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        
        if commit:
            user.save()
            # 기본적으로 모든 신규 사용자는 Viewer 그룹에 추가
            from django.contrib.auth.models import Group
            viewer_group, created = Group.objects.get_or_create(name='Viewer')
            user.groups.add(viewer_group)
        
        return user
