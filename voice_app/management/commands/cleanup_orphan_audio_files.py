import os
from typing import Set

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from voice_app.models import AudioRecord


class Command(BaseCommand):
    help = (
        "Delete orphan files under MEDIA_ROOT/audio that are not referenced by AudioRecord.audio_file. "
        "Defaults to dry-run; pass --execute to actually delete."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually delete files. Default is dry-run.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max number of files to delete (0 = no limit).",
        )
        parser.add_argument(
            "--prefix",
            type=str,
            default="audio/",
            help="Storage prefix to scan (default: audio/).",
        )

    def handle(self, *args, **options):
        execute: bool = options["execute"]
        limit: int = int(options["limit"] or 0)
        prefix: str = (options["prefix"] or "audio/").strip()

        if not prefix.endswith("/"):
            prefix = prefix + "/"

        media_root = getattr(settings, "MEDIA_ROOT", None)
        if not media_root:
            self.stderr.write("[cleanup_orphan_audio_files] ERROR: settings.MEDIA_ROOT is not set")
            return

        base_dir = os.path.join(media_root, prefix.rstrip("/"))
        if not os.path.exists(base_dir):
            self.stdout.write(
                f"[cleanup_orphan_audio_files] prefix={prefix} execute={execute} "
                f"base_dir_missing={base_dir} (nothing to do)"
            )
            return

        referenced: Set[str] = set(
            AudioRecord.objects.exclude(audio_file="")
            .exclude(audio_file__isnull=True)
            .values_list("audio_file", flat=True)
        )

        scanned_files = 0
        orphan_found = 0
        planned = 0
        files_deleted = 0
        missing_files = 0
        file_errors = 0

        self.stdout.write(
            f"[cleanup_orphan_audio_files] prefix={prefix} execute={execute} "
            f"referenced_files={len(referenced)} limit={limit}"
        )

        for root, _dirs, files in os.walk(base_dir):
            for filename in files:
                scanned_files += 1

                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, media_root).replace(os.sep, "/")

                if not rel_path.startswith(prefix):
                    # Safety: only operate within the requested prefix.
                    continue

                if rel_path in referenced:
                    continue

                orphan_found += 1

                if limit and planned >= limit:
                    continue

                planned += 1

                if not execute:
                    self.stdout.write(f"DRY-RUN delete file={rel_path}")
                    continue

                try:
                    if not default_storage.exists(rel_path):
                        missing_files += 1
                        continue
                    default_storage.delete(rel_path)
                    files_deleted += 1
                except Exception as exc:  # noqa: BLE001
                    file_errors += 1
                    self.stderr.write(f"[cleanup_orphan_audio_files] ERROR deleting {rel_path}: {exc}")

        self.stdout.write(
            "[cleanup_orphan_audio_files] done "
            f"scanned_files={scanned_files} orphan_found={orphan_found} planned={planned} "
            f"files_deleted={files_deleted} missing_files={missing_files} file_errors={file_errors}"
        )
