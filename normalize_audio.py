#!/usr/bin/env python3
"""
normalize_audio.py

Script for handling media files:
- convert to MP3 (128 kbps CBR, fixed sample rate)
- normalize loudness to -14.0 LUFS
- replace original file with processed output
- create temp backup/log folder in %TEMP%\YYYY-MM-DD-HH-mm-<scriptname>
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Set, Tuple


# ============================================================
# Config (edit these as needed)
# ============================================================

# Extensions to include for scanning/processing (lowercase, with dot)
INCLUDE_EXTENSIONS: Set[str] = {".m4a", ".wav", ".mp3", ".mp4"}

# Extensions to explicitly exclude (warning will be printed)
EXCLUDE_EXTENSIONS: Set[str] = {
    # ".flac",
    # ".aac",
}

# Processing targets
TARGET_FORMAT = ".mp3"
TARGET_AUDIO_BITRATE = "128k"  # 128 kbps
TARGET_SAMPLE_RATE = 44100     # fixed sample rate (Hz)
TARGET_LUFS = -14.0

# Script behavior
ASK_FOR_INPUT_AT_END = True

# Requested by user: explicit ffmpeg location
FFMPEG_PATH = r"c:\2_Data\C_Config\Libraries\ffmpeg"

# Requested by user: default input if no CLI input is given
DEFAULT_INPUT_PATH = r"C:\Users\Q278022\Downloads\temp\Rauschen - Rosa.wav"

# Primary ffmpeg executable candidate (Windows)
FFMPEG_BIN = str(Path(FFMPEG_PATH) / "ffmpeg.exe")


# ============================================================
# Logging helpers
# ============================================================

class TeeLogger:
    def __init__(self, log_file: Path) -> None:
        self.log_file = log_file
        self._fp = log_file.open("a", encoding="utf-8", newline="\n")

    def write(self, message: str) -> None:
        print(message)
        self._fp.write(message + "\n")
        self._fp.flush()

    def close(self) -> None:
        self._fp.close()


# ============================================================
# Data structures
# ============================================================

@dataclass
class FileResult:
    source: Path
    success: bool
    message: str


# ============================================================
# Utility functions
# ============================================================

def unique_path(path: Path) -> Path:
    """Return a non-conflicting path by appending _1, _2, ... if needed."""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def script_stem() -> str:
    return Path(__file__).stem


def create_temp_work_dir() -> Path:
    now = datetime.now().strftime("%Y-%m-%d-%H-%M")
    folder_name = f"{now}-{script_stem()}"
    work_dir = Path(tempfile.gettempdir()) / folder_name
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def is_supported_media(ext: str) -> bool:
    return ext in {".m4a", ".wav", ".mp3", ".mp4"}


def resolve_ffmpeg_executable() -> Tuple[str | None, str]:
    """
    Try configured ffmpeg path first, then fallback to PATH entry 'ffmpeg'.
    Returns (executable_or_none, info_message).
    """
    candidates = [FFMPEG_BIN, "ffmpeg"]

    for exe in candidates:
        try:
            proc = subprocess.run(
                [exe, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if proc.returncode == 0:
                if exe == FFMPEG_BIN:
                    return exe, f"Using configured ffmpeg: {exe}"
                return exe, f"Configured ffmpeg not available; using ffmpeg from PATH: {exe}"
        except FileNotFoundError:
            continue

    return None, (
        "ffmpeg not found. Tried configured path and PATH fallback.\n"
        f"Configured: {FFMPEG_BIN}\n"
        "Fallback: ffmpeg (PATH)"
    )


def collect_input_files(
    inputs: Iterable[str],
    logger: TeeLogger,
) -> Tuple[List[Path], List[Path], List[Path]]:
    """
    Returns:
      processable_files, excluded_files, unknown_files
    """
    processable: List[Path] = []
    excluded: List[Path] = []
    unknown: List[Path] = []

    seen: Set[Path] = set()

    for raw in inputs:
        p = Path(raw).expanduser().resolve()

        if not p.exists():
            logger.write(f"[WARN] Input does not exist: {p}")
            continue

        candidates: List[Path] = []
        if p.is_file():
            candidates.append(p)
        elif p.is_dir():
            for child in sorted(p.iterdir()):
                if child.is_file():
                    candidates.append(child)
        else:
            logger.write(f"[WARN] Not a file or directory, skipping: {p}")
            continue

        for file_path in candidates:
            if file_path in seen:
                continue
            seen.add(file_path)

            ext = file_path.suffix.lower()

            if ext in EXCLUDE_EXTENSIONS:
                excluded.append(file_path)
                continue

            if ext not in INCLUDE_EXTENSIONS:
                unknown.append(file_path)
                continue

            if not is_supported_media(ext):
                unknown.append(file_path)
                continue

            processable.append(file_path)

    return processable, excluded, unknown


def copy_original_to_backup(src: Path, backup_dir: Path, logger: TeeLogger) -> Path:
    target = unique_path(backup_dir / src.name)
    shutil.copy2(src, target)
    logger.write(f"[INFO] Backup created: {target}")
    return target


def run_ffmpeg_convert_and_normalize(
    ffmpeg_exe: str,
    src: Path,
    dst: Path,
    logger: TeeLogger,
) -> Tuple[bool, str]:
    """
    Convert to MP3 128k CBR, fixed sample rate, normalize to -14 LUFS using loudnorm.
    """
    loudnorm_filter = f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11"

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(src),
        "-vn",
        "-ar", str(TARGET_SAMPLE_RATE),
        "-acodec", "libmp3lame",
        "-b:a", TARGET_AUDIO_BITRATE,
        "-minrate", TARGET_AUDIO_BITRATE,
        "-maxrate", TARGET_AUDIO_BITRATE,
        "-bufsize", "128k",
        "-af", loudnorm_filter,
        str(dst),
    ]

    logger.write(f"[INFO] Running ffmpeg for: {src.name}")
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if proc.returncode != 0:
        err = proc.stderr.strip() or "ffmpeg failed with unknown error"
        return False, err

    return True, "ok"


def process_file(src: Path, work_dir: Path, ffmpeg_exe: str, logger: TeeLogger) -> FileResult:
    try:
        copy_original_to_backup(src, work_dir, logger)

        temp_output = unique_path(work_dir / f"{src.stem}{TARGET_FORMAT}")
        ok, msg = run_ffmpeg_convert_and_normalize(ffmpeg_exe, src, temp_output, logger)
        if not ok:
            return FileResult(src, False, f"Conversion failed: {msg}")

        try:
            src.unlink()
        except Exception as ex:
            return FileResult(src, False, f"Could not remove original file: {ex}")

        final_target = src.with_suffix(TARGET_FORMAT)
        try:
            if final_target.exists():
                final_target = unique_path(final_target)
                logger.write(
                    f"[WARN] Target already exists, using conflict-safe name: {final_target.name}"
                )
            shutil.move(str(temp_output), str(final_target))
        except Exception as ex:
            return FileResult(src, False, f"Could not move processed file into place: {ex}")

        return FileResult(src, True, f"Processed successfully -> {final_target}")

    except Exception as ex:
        return FileResult(src, False, f"Unexpected error: {ex}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert media files to MP3 (128k CBR), normalize to -14 LUFS, and replace originals."
    )
    p.add_argument(
        "inputs",
        nargs="*",
        help="One or more file paths or directory paths; if omitted, DEFAULT_INPUT_PATH is used.",
    )
    return p


def pause_at_end() -> None:
    if ASK_FOR_INPUT_AT_END:
        try:
            input("\nPress Enter to exit...")
        except EOFError:
            pass


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    inputs = args.inputs if args.inputs else [DEFAULT_INPUT_PATH]
    used_default_input = not bool(args.inputs)

    work_dir = create_temp_work_dir()
    log_file = work_dir / "__log.txt"
    logger = TeeLogger(log_file)

    logger.write("===================================================")
    logger.write("normalize_audio.py started")
    logger.write(f"Temp work dir: {work_dir}")
    logger.write(f"Log file: {log_file}")
    logger.write("===================================================")

    ffmpeg_exe, ffmpeg_msg = resolve_ffmpeg_executable()
    if not ffmpeg_exe:
        logger.write(f"[ERROR] {ffmpeg_msg}")
        logger.write("[ERROR] Cannot continue without ffmpeg.")
        logger.close()
        pause_at_end()
        return 1

    logger.write(f"[INFO] {ffmpeg_msg}")

    if used_default_input:
        logger.write(f"[INFO] No input args given; using DEFAULT_INPUT_PATH: {DEFAULT_INPUT_PATH}")

    processable, excluded, unknown = collect_input_files(inputs, logger)

    for p in excluded:
        logger.write(f"[WARN] Excluded by filter: {p}")

    for p in unknown:
        logger.write(f"[WARN] Unknown/unsupported file type: {p}")

    if not processable:
        logger.write("[WARN] No valid files to process.")
        logger.write("[RESULT] SUCCESS (nothing to do)")
        logger.close()
        pause_at_end()
        return 0

    logger.write(f"[INFO] Files to process: {len(processable)}")
    for f in processable:
        logger.write(f"  - {f}")

    results: List[FileResult] = []
    for src in processable:
        result = process_file(src, work_dir, ffmpeg_exe, logger)
        results.append(result)
        if result.success:
            logger.write(f"[OK] {result.source.name}: {result.message}")
        else:
            logger.write(f"[FAIL] {result.source.name}: {result.message}")

    ok_count = sum(1 for r in results if r.success)
    fail_count = len(results) - ok_count

    logger.write("===================================================")
    logger.write(f"[SUMMARY] Processed: {len(results)} | Success: {ok_count} | Failed: {fail_count}")
    if fail_count == 0:
        logger.write("[RESULT] SUCCESS")
        exit_code = 0
    else:
        logger.write("[RESULT] FAILURE")
        exit_code = 1
    logger.write("===================================================")

    logger.close()
    pause_at_end()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())