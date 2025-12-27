# -*- coding: utf-8 -*-
"""Delete AudioRecord rows with missing demographics and delete their media files.

Usage:
  - Dry-run (default):
      python manage.py cleanup_empty_demographics
  - Actually delete:
      python manage.py cleanup_empty_demographics --execute

Options:
  --mode all-empty|any-empty
      all-empty: delete rows where (name, gender, age) are all empty
      any-empty: delete rows where any of (name, gender, age) is empty
  --limit N
      limit number of rows processed (useful for cautious runs)
"""

import os
from typing import Optional

from django.core.management.base import BaseCommand
from django.db.models import Q

from voice_app.models import AudioRecord


def _is_blank_field_q(field_name: str) -> Q:
    return Q(**{f"{field_name}__isnull": True}) | Q(**{field_name: ""})


class Command(BaseCommand):
    help = "(name/gender/age) 비어있는 레코드를 삭제하고 연결된 media/audio 파일도 삭제합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="실제 삭제를 수행합니다 (기본은 dry-run).",
        )
        parser.add_argument(
            "--mode",
            choices=["all-empty", "any-empty"],
            default="all-empty",
            help="삭제 기준: all-empty(세 필드 모두 빈 값) | any-empty(하나라도 빈 값)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="처리할 최대 레코드 수(0이면 제한 없음)",
        )

    def handle(self, *args, **options):
        execute: bool = bool(options.get("execute"))
        mode: str = str(options.get("mode") or "all-empty")
        limit: int = int(options.get("limit") or 0)

        blank_name = _is_blank_field_q("name")
        blank_gender = _is_blank_field_q("gender")
        blank_age = _is_blank_field_q("age")

        if mode == "all-empty":
            q = blank_name & blank_gender & blank_age
        else:
            q = blank_name | blank_gender | blank_age

        qs = AudioRecord.objects.filter(q).order_by("id")
        total = qs.count()

        if limit and limit > 0:
            qs = qs[:limit]

        planned = qs.count()
        self.stdout.write(
            f"[cleanup_empty_demographics] mode={mode} execute={execute} total_matches={total} planned={planned}"
        )

        if planned == 0:
            return

        # preview sample ids
        sample_ids = list(AudioRecord.objects.filter(q).order_by("id").values_list("id", flat=True)[:10])
        self.stdout.write(f"[cleanup_empty_demographics] sample_ids={sample_ids}")

        deleted_rows = 0
        deleted_files = 0
        missing_files = 0
        file_errors = 0

        for record in qs:
            file_name: Optional[str] = None
            abs_path: Optional[str] = None

            try:
                if record.audio_file:
                    file_name = str(record.audio_file.name or "")
                    try:
                        abs_path = record.audio_file.path
                    except Exception:
                        abs_path = None
            except Exception:
                file_name = None
                abs_path = None

            if not execute:
                self.stdout.write(
                    f"DRY-RUN delete id={record.id} identifier={record.identifier} file={file_name or '-'}"
                )
                continue

            # 1) delete file via storage (preferred)
            if record.audio_file and file_name:
                try:
                    # record.audio_file.delete(save=False) removes the file from storage
                    record.audio_file.delete(save=False)
                    deleted_files += 1
                except FileNotFoundError:
                    missing_files += 1
                except Exception as e:
                    file_errors += 1
                    self.stderr.write(f"[WARN] file delete failed id={record.id} file={file_name}: {e}")
                    # fallback: try os.remove if we have a path
                    if abs_path and os.path.exists(abs_path):
                        try:
                            os.remove(abs_path)
                            deleted_files += 1
                        except Exception as e2:
                            file_errors += 1
                            self.stderr.write(f"[WARN] os.remove failed id={record.id} path={abs_path}: {e2}")

            # 2) delete row
            record.delete()
            deleted_rows += 1

        self.stdout.write(
            f"[cleanup_empty_demographics] done rows_deleted={deleted_rows} files_deleted={deleted_files} missing_files={missing_files} file_errors={file_errors}"
        )
