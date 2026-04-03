import datetime
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from voice_app.models import AudioRecord


def _parse_date(value: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise CommandError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc


def _safe_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _compute_age_years_months(birth_date: datetime.date, on_date: datetime.date) -> Tuple[int, int]:
    if on_date < birth_date:
        return 0, 0

    total_months = (on_date.year - birth_date.year) * 12 + (on_date.month - birth_date.month)
    if on_date.day < birth_date.day:
        total_months -= 1

    years = total_months // 12
    months = total_months % 12
    return years, months


def _extract_birth_date(audio: AudioRecord) -> Optional[datetime.date]:
    year = _safe_int(audio.birth_year)
    month = _safe_int(audio.birth_month)
    day = _safe_int(audio.birth_day)
    if not (year and month and day):
        return None
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def _extract_age_in_months(audio: AudioRecord) -> Optional[int]:
    if audio.age_in_months is not None:
        return int(audio.age_in_months)

    data = audio.category_specific_data or {}
    for key in ("age_in_months", "age_months", "months_old"):
        value = data.get(key)
        try:
            if value is not None and str(value).strip() != "":
                return int(value)
        except (ValueError, TypeError):
            continue
    return None


def _age_matches(
    audio: AudioRecord,
    *,
    on_date: datetime.date,
    target_years: Optional[int],
    target_months: Optional[int],
    target_birth_date: Optional[datetime.date],
) -> bool:
    if target_birth_date is not None:
        birth_date = _extract_birth_date(audio)
        return birth_date == target_birth_date

    if target_years is None or target_months is None:
        return True

    birth_date = _extract_birth_date(audio)
    if birth_date is not None:
        years, months = _compute_age_years_months(birth_date, on_date)
        return years == target_years and months == target_months

    age_in_months = _extract_age_in_months(audio)
    if age_in_months is not None:
        return age_in_months == (target_years * 12 + target_months)

    # Fallback: some datasets store age as a formatted string in `age`, e.g. "60세 8개월".
    # We normalize whitespace for safety.
    if getattr(audio, "age", None):
        expected = f"{target_years}세 {target_months}개월"
        actual = " ".join(str(audio.age).split())
        return actual == expected

    return False


class Command(BaseCommand):
    help = "Purge AudioRecord rows and their media files by criteria (safe dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--created-date",
            required=False,
            help="Upload date to match (YYYY-MM-DD), matched against created_at__date",
        )
        parser.add_argument(
            "--created-date-from",
            required=False,
            help="Start upload date (YYYY-MM-DD), inclusive. Use with --created-date-to.",
        )
        parser.add_argument(
            "--created-date-to",
            required=False,
            help="End upload date (YYYY-MM-DD), inclusive. Use with --created-date-from.",
        )
        parser.add_argument("--name", default=None, help="Exact name to match (optional)")
        parser.add_argument(
            "--name-contains",
            default=None,
            help="Substring match for name (case-insensitive).",
        )
        parser.add_argument(
            "--name-missing",
            action="store_true",
            help="Match rows where name is NULL or empty string.",
        )
        parser.add_argument("--gender", default=None, help="Exact gender to match (optional, e.g., 남)")

        parser.add_argument(
            "--age-exact",
            default=None,
            help="Exact age string to match (e.g., 'unknown' or '5세 8개월').",
        )
        parser.add_argument(
            "--age-missing",
            action="store_true",
            help="Match rows where age is NULL or empty string.",
        )

        parser.add_argument("--age-years", type=int, default=None, help="Target age years (optional)")
        parser.add_argument("--age-months", type=int, default=None, help="Target age months (optional)")
        parser.add_argument("--birth-date", default=None, help="Exact birth date to match (YYYY-MM-DD). If provided, age-years/months are ignored.")

        parser.add_argument("--include-non-wav", action="store_true", help="Include non-wav audio_file types (default: wav only)")

        parser.add_argument(
            "--max-print",
            type=int,
            default=200,
            help="Max number of matched rows to print (default: 200). Use --max-print 0 to print none.",
        )
        parser.add_argument("--print-all", action="store_true", help="Print all matched rows (can be very verbose)")

        parser.add_argument("--execute", action="store_true", help="Actually delete DB rows and files")
        parser.add_argument("--yes", action="store_true", help="Required with --execute to confirm destructive action")

    def handle(self, *args, **options):
        created_date_raw = options.get("created_date")
        created_from_raw = options.get("created_date_from")
        created_to_raw = options.get("created_date_to")

        if created_date_raw and (created_from_raw or created_to_raw):
            raise CommandError("Use either --created-date OR (--created-date-from and --created-date-to), not both.")

        if created_date_raw:
            created_date = _parse_date(created_date_raw)
            created_date_from = None
            created_date_to = None
        else:
            if not (created_from_raw and created_to_raw):
                raise CommandError("Provide --created-date, or both --created-date-from and --created-date-to.")
            created_date_from = _parse_date(created_from_raw)
            created_date_to = _parse_date(created_to_raw)
            if created_date_from > created_date_to:
                raise CommandError("--created-date-from must be <= --created-date-to")
            created_date = None
        name = (options.get("name") or "").strip() or None
        name_contains = options.get("name_contains")
        if isinstance(name_contains, str):
            name_contains = name_contains.strip() or None
        name_missing = bool(options.get("name_missing"))
        gender = (options.get("gender") or "").strip() or None
        age_exact = options.get("age_exact")
        if isinstance(age_exact, str):
            age_exact = age_exact.strip() or None
        age_missing = bool(options.get("age_missing"))
        include_non_wav = bool(options["include_non_wav"])
        max_print = int(options.get("max_print") or 0)
        print_all = bool(options.get("print_all"))

        target_birth_date = _parse_date(options["birth_date"]) if options.get("birth_date") else None
        target_years = options.get("age_years")
        target_months = options.get("age_months")

        if sum([1 if name is not None else 0, 1 if name_contains is not None else 0, 1 if name_missing else 0]) > 1:
            raise CommandError("Use only one of: --name, --name-contains, --name-missing")

        if age_missing and age_exact is not None:
            raise CommandError("Use either --age-exact or --age-missing, not both.")

        if target_birth_date is None and (target_years is None) != (target_months is None):
            raise CommandError("Provide both --age-years and --age-months, or neither. (Or use --birth-date)")

        filters = {}
        if created_date is not None:
            filters["created_at__date"] = created_date
        else:
            filters["created_at__date__range"] = (created_date_from, created_date_to)
        if gender is not None:
            filters["gender"] = gender

        qs = AudioRecord.objects.filter(**filters)

        if name_missing:
            qs = qs.filter(Q(name__isnull=True) | Q(name=""))
        elif name_contains is not None:
            qs = qs.filter(name__icontains=name_contains)
        elif name is not None:
            qs = qs.filter(name=name)

        if age_missing:
            qs = qs.filter(Q(age__isnull=True) | Q(age=""))
        elif age_exact is not None:
            # Treat "unknown" as semantically missing in addition to the literal string.
            if age_exact.lower() == "unknown":
                qs = qs.filter(Q(age__iexact="unknown") | Q(age__isnull=True) | Q(age=""))
            else:
                qs = qs.filter(age=age_exact)
        if not include_non_wav:
            qs = qs.filter(audio_file__iendswith=".wav")

        candidates: list[AudioRecord] = []
        total_bytes = 0

        self.stdout.write(self.style.MIGRATE_HEADING("[purge_audio_records] DRY RUN" if not options["execute"] else "[purge_audio_records] EXECUTE"))
        date_part = (
            f"created_date={created_date}" if created_date is not None else f"created_date_range={created_date_from}..{created_date_to}"
        )
        self.stdout.write(
            "Criteria: {date_part}, name={name}, gender={gender}, wav_only={wav_only}".format(
                date_part=date_part,
                name=(
                    "(missing)"
                    if name_missing
                    else (f"(contains '{name_contains}')" if name_contains is not None else (f"'{name}'" if name is not None else "(any)"))
                ),
                gender=(f"'{gender}'" if gender is not None else "(any)"),
                wav_only=(not include_non_wav),
            )
        )
        if age_missing:
            self.stdout.write("Age exact filter: (missing)")
        elif age_exact is not None:
            self.stdout.write(f"Age exact filter: '{age_exact}'")
        if target_birth_date is not None:
            self.stdout.write(f"Age filter: birth_date == {target_birth_date}")
        elif target_years is not None:
            self.stdout.write(f"Age filter: {target_years} years {target_months} months (computed from birth_date if available, else age_in_months)")
        else:
            self.stdout.write("Age filter: (none)")

        printed = 0
        total_matched = 0
        # Age computed-from-birth uses an anchor date; if we are deleting by a date range
        # we use each record's local created date for consistency.
        for audio in qs.order_by("id"):
            created_local_date = timezone.localtime(audio.created_at).date() if audio.created_at else None
            age_anchor_date = created_date if created_date is not None else (created_local_date or timezone.localdate())
            if not _age_matches(
                audio,
                on_date=age_anchor_date,
                target_years=target_years,
                target_months=target_months,
                target_birth_date=target_birth_date,
            ):
                continue

            file_path = None
            exists = False
            size = 0
            try:
                file_path = audio.audio_file.path
                exists = os.path.exists(file_path)
                if exists:
                    size = os.path.getsize(file_path)
            except Exception:
                file_path = getattr(audio.audio_file, "name", None)

            birth_date = _extract_birth_date(audio)
            candidates.append(audio)
            total_bytes += size
            total_matched += 1

            should_print = print_all or (max_print > 0 and printed < max_print)
            if should_print:
                self.stdout.write(
                    f"- id={audio.id} created_at={created_local_date} category={audio.category} identifier={audio.identifier or ''} "
                    f"name={audio.name or ''} gender={audio.gender or ''} birth={birth_date or ''} "
                    f"file={file_path or ''} exists={exists} bytes={size}"
                )
                printed += 1

        if not print_all and max_print > 0 and total_matched > printed:
            self.stdout.write(self.style.WARNING(f"... {total_matched - printed} more matched rows not shown (use --print-all)."))

        self.stdout.write(self.style.WARNING(f"Matched candidates: {len(candidates)}"))
        self.stdout.write(self.style.WARNING(f"Total file size: {total_bytes / (1024 * 1024):.2f} MB"))

        if not options["execute"]:
            self.stdout.write("\nNo changes made (dry-run). To delete, re-run with: --execute --yes")
            return

        if not options["yes"]:
            raise CommandError("Refusing to delete without --yes. (Use --execute --yes)")

        if not candidates:
            self.stdout.write("Nothing to delete.")
            return

        # Optional sqlite backup (best-effort)
        try:
            db = settings.DATABASES.get("default", {})
            engine = (db.get("ENGINE") or "").lower()
            if engine.endswith("sqlite3"):
                db_path = Path(db.get("NAME"))
                if db_path.exists():
                    backup_dir = Path(getattr(settings, "BASE_DIR", Path.cwd())) / "backups"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = backup_dir / f"{db_path.name}.backup_before_purge_{ts}"
                    shutil.copy2(db_path, backup_path)
                    self.stdout.write(self.style.SUCCESS(f"SQLite DB backup created: {backup_path}"))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"DB backup skipped (non-fatal): {type(exc).__name__}: {exc}"))

        deleted_files = 0
        missing_files = 0

        with transaction.atomic():
            for audio in candidates:
                # Delete file first (storage-aware), then DB row.
                try:
                    path = audio.audio_file.path
                    if os.path.exists(path):
                        audio.audio_file.delete(save=False)
                        deleted_files += 1
                    else:
                        missing_files += 1
                except Exception:
                    # If storage/path is not accessible, still delete DB row.
                    missing_files += 1

                audio.delete()

        self.stdout.write(self.style.SUCCESS(f"Deleted rows: {len(candidates)}"))
        self.stdout.write(self.style.SUCCESS(f"Deleted files: {deleted_files}, missing/unresolved files: {missing_files}"))
