#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find duplicate/stale bot launchers around the checkout without executing them."""
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

PATTERNS = ("ICT Algo Master", "진행", "לـ 30", "فحص الشموع (", "Live Trading Simulator")
SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "data"}
root = Path(__file__).resolve().parents[1]
search_root = root.parent  # catches sibling copies such as "b-arena... (2)"
print(f"Python: {sys.executable}")
print(f"Correct repository: {root}")
try:
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], text=True).strip()
except Exception:
    commit = "unknown"
print(f"Correct Git commit: {commit}")
print(f"Correct launcher: {root / 'main.py'}")
print(f"Searching safely under: {search_root}\n")
found = []
for path in search_root.rglob("*.py"):
    if path.resolve() == Path(__file__).resolve():
        continue
    if any(part in SKIP for part in path.parts):
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    hits = [p for p in PATTERNS if p in text]
    if hits:
        found.append((path, hits))
if not found:
    print("No Python source containing the foreign banner was found.")
    print("It may be an .exe, cached terminal output, or a file outside this parent folder.")
else:
    print("FILES THAT CAN PRODUCE THE SHOWN CONSOLE:")
    for path, hits in found:
        marker = "CORRECT REPO" if root in path.parents else "OTHER COPY"
        print(f"- [{marker}] {path}")
        print(f"  matched: {', '.join(repr(x) for x in hits)}")
    print("\nDo not delete anything yet. Send this output and the matched file for audit.")
