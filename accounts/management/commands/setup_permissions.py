# accounts/management/commands/setup_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from voice_app.models import AudioRecord


class Command(BaseCommand):
    help = '사용자 권한 그룹 설정 (Editor, Viewer)'

    def handle(self, *args, **kwargs):
        # ContentType 가져오기
        content_type = ContentType.objects.get_for_model(AudioRecord)
        
        # ========== Viewer 그룹 (읽기 전용) ==========
        viewer_group, created = Group.objects.get_or_create(name='Viewer')
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Viewer 그룹 생성됨'))
        else:
            self.stdout.write('Viewer 그룹이 이미 존재합니다.')
        
        # Viewer 권한: 읽기만 가능
        viewer_permissions = Permission.objects.filter(
            content_type=content_type,
            codename__in=['view_audiorecord']
        )
        viewer_group.permissions.set(viewer_permissions)
        self.stdout.write(self.style.SUCCESS(f'  - Viewer 권한: 데이터 조회만 가능'))
        
        # ========== Editor 그룹 (수정 가능) ==========
        editor_group, created = Group.objects.get_or_create(name='Editor')
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Editor 그룹 생성됨'))
        else:
            self.stdout.write('Editor 그룹이 이미 존재합니다.')
        
        # Editor 권한: 모든 CRUD 작업 가능
        editor_permissions = Permission.objects.filter(
            content_type=content_type,
            codename__in=[
                'add_audiorecord',
                'change_audiorecord',
                'delete_audiorecord',
                'view_audiorecord'
            ]
        )
        editor_group.permissions.set(editor_permissions)
        self.stdout.write(self.style.SUCCESS(f'  - Editor 권한: 데이터 추가/수정/삭제/조회 가능'))
        
        self.stdout.write(self.style.SUCCESS('\n권한 설정 완료!'))
        self.stdout.write('\n사용법:')
        self.stdout.write('  - 신규 사용자는 자동으로 Viewer 그룹에 추가됩니다.')
        self.stdout.write('  - 관리자 페이지에서 사용자를 Editor 그룹에 추가하여 수정 권한을 부여하세요.')
        self.stdout.write('  - URL: http://210.125.93.241:8010/admin/')
