#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> int:
    proc = subprocess.run(cmd)
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Transcribe wav files that are missing matching .txt using the whisper CLI. "
            "By default, writes .txt next to each wav (via per-file output_dir)."
        )
    )
    parser.add_argument(
        "--list",
        default="analysis/senior_paragraph_wavs_missing_txt.txt",
        help="Path to a newline-delimited list of wav paths (workspace-relative).",
    )
    parser.add_argument(
        "--model",
        default="small",
        help="Whisper model name (e.g., base, small, medium, large-v2).",
    )
    parser.add_argument(
        "--language",
        default="ko",
        help="Language code passed to whisper (e.g., ko).",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Optional whisper --device value (e.g., cpu, cuda). If omitted, whisper decides.",
    )
    parser.add_argument(
        "--fp16",
        default=None,
        choices=["true", "false"],
        help="Optional whisper --fp16 true/false. If omitted, whisper default is used.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would run, without executing.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If >0, only process the first N files.",
    )

    args = parser.parse_args()

    workspace = Path.cwd()
    list_path = workspace / args.list
    if not list_path.exists():
        print(f"List file not found: {list_path}", file=sys.stderr)
        return 2

    wavs = [
        line.strip()
        for line in list_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]

    if args.limit and args.limit > 0:
        wavs = wavs[: args.limit]

    if not wavs:
        print("No wavs to process.")
        return 0

    failures: list[tuple[str, int]] = []

    for idx, wav_rel in enumerate(wavs, 1):
        wav_path = (workspace / wav_rel).resolve()
        if wav_path.suffix.lower() != ".wav":
            continue

        txt_path = wav_path.with_suffix(".txt")
        if txt_path.exists():
            print(f"[{idx}/{len(wavs)}] SKIP exists: {txt_path}")
            continue

        out_dir = str(wav_path.parent)

        cmd: list[str] = [
            "whisper",
            str(wav_path),
            "--model",
            args.model,
            "--language",
            args.language,
            "--task",
            "transcribe",
            "--output_format",
            "txt",
            "--output_dir",
            out_dir,
        ]

        if args.device:
            cmd += ["--device", args.device]
        if args.fp16 is not None:
            cmd += ["--fp16", args.fp16]

        pretty = " ".join(shlex.quote(c) for c in cmd)
        print(f"[{idx}/{len(wavs)}] RUN: {pretty}")

        if args.dry_run:
            continue

        rc = run(cmd)
        if rc != 0:
            failures.append((wav_rel, rc))
            print(f"[{idx}/{len(wavs)}] FAIL rc={rc}: {wav_rel}", file=sys.stderr)

    if failures:
        fail_path = workspace / "analysis" / "whisper_transcribe_failures.tsv"
        fail_path.write_text(
            "wav\trc\n" + "\n".join(f"{w}\t{rc}" for w, rc in failures) + "\n",
            encoding="utf-8",
        )
        print(f"Failures: {len(failures)} (see {fail_path})", file=sys.stderr)
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
