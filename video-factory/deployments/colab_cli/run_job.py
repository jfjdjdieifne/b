#!/usr/bin/env python3
"""Safely execute a file-producing job through the official Google Colab CLI.

Lifecycle: allocate -> execute -> download -> stop. The runtime is stopped in a
finally block even when execution or artifact retrieval fails. Google Drive and
browser automation are intentionally not used.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def command(colab: str, *args: str) -> list[str]:
    return [colab, "--auth=oauth2", *args]


def run_checked(args: list[str]) -> None:
    subprocess.run(args, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("script", type=Path, help="Local Python file to execute remotely")
    parser.add_argument("remote_output", help="Result path in the Colab VM")
    parser.add_argument("output", type=Path, help="Local destination path")
    parser.add_argument("--gpu", default="T4", choices=("T4", "L4", "G4", "A100", "H100"))
    parser.add_argument("--session", default="")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument(
        "--keep-on-failure",
        action="store_true",
        help="Debug only: leave the VM allocated after a failed job",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.script.is_file():
        raise SystemExit(f"Script does not exist: {args.script}")
    if args.timeout < 30:
        raise SystemExit("--timeout must be at least 30 seconds")

    colab = os.getenv("COLAB_BIN", "colab")
    resolved = shutil.which(colab)
    if resolved is None:
        raise SystemExit(
            "colab CLI not found. Install deployments/colab_cli/requirements-local.txt"
        )
    colab = resolved
    session = args.session or f"vf-{int(time.time())}"
    allocated = False
    succeeded = False
    temp_output = args.output.with_suffix(args.output.suffix + ".part")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp_output.unlink(missing_ok=True)

    try:
        run_checked(command(colab, "new", "-s", session, "--gpu", args.gpu))
        allocated = True
        run_checked(
            command(
                colab,
                "exec",
                "-s",
                session,
                "-f",
                str(args.script.resolve()),
                "--timeout",
                str(args.timeout),
            )
        )
        run_checked(
            command(
                colab,
                "download",
                "-s",
                session,
                args.remote_output,
                str(temp_output.resolve()),
            )
        )
        if not temp_output.is_file() or temp_output.stat().st_size == 0:
            raise RuntimeError("Colab returned an empty artifact")
        temp_output.replace(args.output)
        succeeded = True
        print(f"COLAB_JOB_OUTPUT={args.output.resolve()}")
        return 0
    finally:
        temp_output.unlink(missing_ok=True)
        should_stop = allocated and (succeeded or not args.keep_on_failure)
        if should_stop:
            stopped = subprocess.run(command(colab, "stop", "-s", session), check=False)
            if stopped.returncode and succeeded:
                print(
                    f"WARNING: job succeeded but session cleanup failed: {session}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())
