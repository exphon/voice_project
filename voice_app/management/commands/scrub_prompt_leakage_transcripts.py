# -*- coding: utf-8 -*-

import os
import shutil
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from voice_app.models import AudioRecord
from voice_app.whisper_utils import _scrub_prompt_leakage


class Command(BaseCommand):
    help = "전사 텍스트에서 Whisper 프롬프트(지시문) 유출 문구를 일괄 제거합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="실제로 DB를 업데이트합니다. 미지정 시 dry-run(변경 없음)으로 동작합니다.",
        )
        parser.add_argument(
            "--include-manual",
            action="store_true",
            help="manual_transcript도 함께 정리합니다.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="처리할 최대 레코드 수(0이면 제한 없음)",
        )
        parser.add_argument(
            "--no-backup",
            action="store_true",
            help="SQLite DB 백업을 만들지 않습니다(--apply일 때만 의미 있음).",
        )

    def _maybe_backup_sqlite(self):
        db = settings.DATABASES.get("default", {})
        if db.get("ENGINE") != "django.db.backends.sqlite3":
            return None

        db_path = str(db.get("NAME") or "")
        if not db_path or not os.path.exists(db_path):
            return None

        backups_dir = os.path.join(str(settings.BASE_DIR), "backups")
        os.makedirs(backups_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backups_dir, f"db.sqlite3.backup_before_scrub_prompt_{ts}")
        shutil.copy2(db_path, backup_path)
        return backup_path

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        include_manual = bool(options.get("include_manual"))
        limit = int(options.get("limit") or 0)
        no_backup = bool(options.get("no_backup"))

        needles = [
            "한국어 외 언어로 출력하지 마세요",
            "외국어로 출력하지 마세요",
            "일본어/영어/중국어",
            "다음은 한국어 음성의 전사",
            "한국어로만 전사하세요",
            "음성에 없는 문장은 쓰지 마세요",
        ]

        query = Q()
        for n in needles:
            query |= Q(transcript__icontains=n)
            if include_manual:
                query |= Q(manual_transcript__icontains=n)

        qs = AudioRecord.objects.filter(query).order_by("id")
        if limit > 0:
            qs = qs[:limit]

        total_candidates = qs.count()
        if total_candidates == 0:
            self.stdout.write(self.style.SUCCESS("대상 레코드가 없습니다."))
            return

        self.stdout.write(f"대상 레코드(필터 매칭): {total_candidates}")
        self.stdout.write(f"모드: {'APPLY' if apply_changes else 'DRY-RUN'} / include_manual={include_manual}")

        backup_path = None
        if apply_changes and not no_backup:
            backup_path = self._maybe_backup_sqlite()
            if backup_path:
                self.stdout.write(self.style.WARNING(f"SQLite 백업 생성: {backup_path}"))
            else:
                self.stdout.write(self.style.WARNING("SQLite 백업을 생성하지 못했습니다(비-SQLite 또는 파일 미존재)."))

        changed_transcript = 0
        changed_manual = 0

        with transaction.atomic():
            for record in qs.iterator(chunk_size=200):
                update_fields = []

                old_auto = record.transcript
                if old_auto:
                    new_auto = _scrub_prompt_leakage(old_auto)
                    if new_auto != old_auto:
                        record.transcript = new_auto
                        update_fields.append("transcript")
                        changed_transcript += 1

                if include_manual:
                    old_manual = record.manual_transcript
                    if old_manual:
                        new_manual = _scrub_prompt_leakage(old_manual)
                        if new_manual != old_manual:
                            record.manual_transcript = new_manual
                            update_fields.append("manual_transcript")
                            changed_manual += 1

                if apply_changes and update_fields:
                    record.save(update_fields=update_fields)

            if not apply_changes:
                # dry-run이면 트랜잭션 롤백
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"변경 예정/적용 건수: transcript={changed_transcript}, manual_transcript={changed_manual}"
        ))

        if not apply_changes:
            self.stdout.write("실제 반영하려면: python manage.py scrub_prompt_leakage_transcripts --apply --include-manual")
        elif backup_path:
            self.stdout.write(self.style.WARNING(f"문제 시 백업으로 복구 가능: {backup_path}"))
