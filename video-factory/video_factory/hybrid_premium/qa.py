from __future__ import annotations
import json, re, subprocess
from pathlib import Path
import cv2, numpy as np
from .renderer import find_ffmpeg

def longest(x):
    b = c = 0
    for v in x:
        c = c + 1 if v else 0
        b = max(b, c)
    return b

def analyze_video(path, *, expected_duration, expected_width=1080, expected_height=1920, expected_fps=30.0, freeze_seconds=.5, low_motion_mae=.5):
    p = Path(path).resolve()
    cap = cv2.VideoCapture(str(p))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    declared = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    f = []
    while True:
        ok, x = cap.read()
        if not ok:
            break
        f.append(cv2.resize(cv2.cvtColor(x, cv2.COLOR_BGR2GRAY), (180, 320)))
    cap.release()
    a = np.stack(f)
    d = np.array([np.mean(cv2.absdiff(a[i], a[i - 1])) for i in range(1, len(a))])
    black = (a < 8).mean((1, 2))
    dur = float(len(a) / fps)
    
    r = subprocess.run([find_ffmpeg(), '-hide_banner', '-i', str(p), '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True)
    iv = re.findall(r'I:\s+(-?[0-9.]+) LUFS', r.stderr)
    pv = re.findall(r'Peak:\s+(-?[0-9.]+) dBFS', r.stderr)
    il = float(iv[-1]) if iv else None
    tp = float(pv[-1]) if pv else None
    low = float(longest(d < low_motion_mae) / fps)
    
    checks = {
        'duration': bool(abs(dur - expected_duration) <= max(.04, 1 / fps)),
        'resolution': bool((w, h) == (expected_width, expected_height)),
        'fps': bool(abs(fps - expected_fps) <= .05),
        'decodable_frames': bool(len(a) == declared),
        'no_freeze_over_threshold': bool(low < freeze_seconds),
        'no_full_black_frame': bool(float(black.max()) < .98),
        'safe_true_peak': bool(tp is None or tp <= -1)
    }
    
    return {
        'pass': bool(all(checks.values())),
        'checks': checks,
        'file': str(p),
        'bytes': p.stat().st_size,
        'duration': dur,
        'width': w,
        'height': h,
        'fps': fps,
        'frame_count': len(a),
        'median_frame_difference': float(np.median(d)),
        'longest_low_motion_seconds': low,
        'maximum_black_fraction': float(black.max()),
        'integrated_lufs': il,
        'true_peak_dbfs': tp
    }

def write_report(m, json_path, markdown_path):
    Path(json_path).write_text(json.dumps(m, indent=2))
    Path(markdown_path).write_text('# Hybrid Premium QA\n\n**' + ('PASS' if m['pass'] else 'FAIL') + '**\n')
