#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from management_policy_comparison import compare_bundle

parser = argparse.ArgumentParser()
parser.add_argument("bundle", help="WFT directory or extracted ZIP directory")
parser.add_argument("--count", type=int, default=5)
parser.add_argument("--output", default=None)
args = parser.parse_args()
result = compare_bundle(args.bundle, args.count, args.output)
print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
print("Saved", result["saved_to"])
