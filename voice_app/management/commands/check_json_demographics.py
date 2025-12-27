import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Set, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand


TARGET_KEYS: Set[str] = {"name", "gender", "age", "이름", "성별", "나이"}
PRIMARY_KEYS: Tuple[str, str, str] = ("name", "gender", "age")


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def _find_key_values(obj: Any, keys: Set[str], found: Dict[str, Any]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys and key not in found and _is_non_empty(value):
                found[key] = value
            _find_key_values(value, keys, found)
    elif isinstance(obj, list):
        for item in obj:
            _find_key_values(item, keys, found)


@dataclass
class FileResult:
    path: str
    ok_all_three: bool
    found: Dict[str, Any]
    error: Optional[str] = None


class Command(BaseCommand):
    help = (
        "Scan JSON files under MEDIA_ROOT/audio for demographics fields (name/gender/age). "
        "Reports how many files contain the values (anywhere in the JSON)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--prefix",
            type=str,
            default="audio/",
            help="Relative directory under MEDIA_ROOT to scan (default: audio/).",
        )
        parser.add_argument(
            "--max-files",
            type=int,
            default=0,
            help="Stop after scanning N files (0 = no limit).",
        )
        parser.add_argument(
            "--print-missing",
            action="store_true",
            help="Print sample file paths missing one or more of name/gender/age.",
        )
        parser.add_argument(
            "--sample",
            type=int,
            default=20,
            help="How many sample paths to print (default 20).",
        )

    def handle(self, *args, **options):
        prefix: str = (options["prefix"] or "audio/").strip()
        max_files: int = int(options["max_files"] or 0)
        print_missing: bool = bool(options["print_missing"])
        sample: int = int(options["sample"] or 20)

        if not prefix.endswith("/"):
            prefix += "/"

        media_root = getattr(settings, "MEDIA_ROOT", None)
        if not media_root:
            self.stderr.write("[check_json_demographics] ERROR: settings.MEDIA_ROOT is not set")
            return

        base_dir = os.path.join(media_root, prefix.rstrip("/"))
        if not os.path.exists(base_dir):
            self.stdout.write(
                f"[check_json_demographics] base_dir_missing={base_dir} (nothing to scan)"
            )
            return

        total = 0
        ok_all_three = 0
        missing_any = 0
        empty_files = 0
        parse_errors = 0

        ok_paths = []
        missing_key_paths = []
        empty_or_parse_error_paths = []

        def should_stop() -> bool:
            return bool(max_files and total >= max_files)

        self.stdout.write(
            f"[check_json_demographics] scanning={base_dir} prefix={prefix} max_files={max_files or '∞'}"
        )

        for root, _dirs, files in os.walk(base_dir):
            for filename in files:
                if not filename.lower().endswith(".json"):
                    continue

                if should_stop():
                    break

                total += 1
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, media_root).replace(os.sep, "/")

                try:
                    if os.path.getsize(abs_path) == 0:
                        empty_files += 1
                        if len(empty_or_parse_error_paths) < sample:
                            empty_or_parse_error_paths.append(f"{rel_path} (EMPTY_FILE)")
                        continue
                except OSError as exc:
                    parse_errors += 1
                    if len(empty_or_parse_error_paths) < sample:
                        empty_or_parse_error_paths.append(f"{rel_path} (STAT_ERROR: {exc})")
                    continue

                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as exc:  # noqa: BLE001
                    parse_errors += 1
                    if len(empty_or_parse_error_paths) < sample:
                        empty_or_parse_error_paths.append(f"{rel_path} (PARSE_ERROR: {exc})")
                    continue

                found: Dict[str, Any] = {}
                _find_key_values(data, TARGET_KEYS, found)

                # Normalize Korean keys to primary keys if primary missing.
                if "name" not in found and "이름" in found:
                    found["name"] = found["이름"]
                if "gender" not in found and "성별" in found:
                    found["gender"] = found["성별"]
                if "age" not in found and "나이" in found:
                    found["age"] = found["나이"]

                has_all_three = all(k in found and _is_non_empty(found.get(k)) for k in PRIMARY_KEYS)

                if has_all_three:
                    ok_all_three += 1
                    if len(ok_paths) < sample:
                        ok_paths.append(
                            f"{rel_path} -> name={found.get('name')} gender={found.get('gender')} age={found.get('age')}"
                        )
                else:
                    missing_any += 1
                    if len(missing_key_paths) < sample:
                        missing_keys = [k for k in PRIMARY_KEYS if not _is_non_empty(found.get(k))]
                        missing_key_paths.append(
                            f"{rel_path} missing={missing_keys} found_keys={sorted(found.keys())}"
                        )

            if should_stop():
                break

        self.stdout.write(
            "[check_json_demographics] done "
            f"total_json={total} ok_all_three={ok_all_three} missing_any={missing_any} "
            f"empty_files={empty_files} parse_errors={parse_errors}"
        )

        if ok_paths:
            self.stdout.write("[check_json_demographics] sample_ok:")
            for line in ok_paths:
                self.stdout.write(f"  {line}")

        if print_missing and missing_key_paths:
            self.stdout.write("[check_json_demographics] sample_missing_keys:")
            for line in missing_key_paths:
                self.stdout.write(f"  {line}")

        if print_missing and empty_or_parse_error_paths:
            self.stdout.write("[check_json_demographics] sample_empty_or_parse_errors:")
            for line in empty_or_parse_error_paths:
                self.stdout.write(f"  {line}")
