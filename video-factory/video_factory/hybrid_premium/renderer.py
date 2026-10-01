from __future__ import annotations
import hashlib, json, os, shutil, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
from .plan import EditPlan, Shot

GRADES = {
    'neutral': 'eq=contrast=1.04:saturation=.92:brightness=-.01,vignette=PI/5.8',
    'desert': 'eq=contrast=1.10:saturation=.74:brightness=-.045:gamma=.94,colorbalance=rs=.055:gs=.015:bs=-.055,vignette=PI/5',
    'dig': 'eq=contrast=1.14:saturation=.60:brightness=-.055:gamma=.96,colorbalance=rs=.045:gs=.008:bs=-.035,vignette=PI/5.5',
    'inscription': 'eq=contrast=1.20:saturation=.26:brightness=-.085:gamma=.94,colorbalance=rs=.03:gs=.015:bs=-.045,vignette=PI/4.8',
    'cave': 'eq=contrast=1.18:saturation=.30:brightness=-.065:gamma=.92,colorbalance=rs=.025:gs=.012:bs=-.018,vignette=PI/4.2',
    'breath': "eq=contrast=1.22:saturation=.26:brightness='-0.085+0.022*sin(2*PI*t/1.25)':gamma=.90:eval=frame,colorbalance=rs=.025:gs=.012:bs=-.02,vignette=PI/3.8"
}

def find_ffmpeg():
    if os.getenv('FFMPEG_BINARY'):
        return os.environ['FFMPEG_BINARY']
    if shutil.which('ffmpeg'):
        return shutil.which('ffmpeg')
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def crop(s: Shot):
    if s.crop_x is not None:
        return f"crop=ih*9/16:ih:'{s.crop_x}+({s.reframe_pixels})*t/{s.duration}':0," if s.reframe_pixels else f'crop=ih*9/16:ih:{s.crop_x}:0,'
    if s.zoom_crop is not None:
        return f'crop=iw*{s.zoom_crop}:ih*{s.zoom_crop}:(iw-iw*{s.zoom_crop})/2:0,'
    return ''

def build_filtergraph(p: EditPlan, ni, mi):
    c = []
    labs = []
    for i, s in enumerate(p.shots):
        if s.grade not in GRADES:
            raise ValueError('Unknown grade ' + s.grade)
        c.append(f'[{i}:v]setpts=PTS-STARTPTS,fps={p.fps},{crop(s)}scale={p.width}:{p.height}:flags=lanczos,setsar=1,{GRADES[s.grade]},format=yuv420p[v{i}]')
        labs.append(f'[v{i}]')
    c.append(''.join(labs) + f'concat=n={len(labs)}:v=1:a=0,format=yuv420p[base]')
    cur = 'base'
    for j, x in enumerate(p.effects):
        out = f'fx{j}'
        c.append(f"[{cur}]drawbox=x=0:y=0:w=iw:h=ih:color={x.get('color','white')}@{x.get('opacity',.62)}:t=fill:enable='between(t,{x['start']},{x['end']})'[{out}]")
        cur = out
    if p.captions:
        q = str(p.resolve(p.captions)).replace('\\', '/').replace(':', '\\:')
        c.append(f"[{cur}]subtitles='{q}':fontsdir='/usr/share/fonts/truetype/dejavu'[vout]")
    else:
        c.append(f'[{cur}]null[vout]')

    audio = False
    if ni is not None and mi is not None:
        c += [
            f'[{ni}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,pan=stereo|c0=c0|c1=c0[nar]',
            f'[{mi}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[bed]',
            '[nar][bed]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=8[aout]'
        ]
        audio = True
    elif ni is not None:
        c += [
            f'[{ni}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aout]'
        ]
        audio = True
    elif mi is not None:
        c += [
            f'[{mi}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aout]'
        ]
        audio = True

    return ';\n'.join(c) + '\n', audio

def build_command(p: EditPlan, out: Path, preview=False):
    p.validate()
    cmd = [find_ffmpeg(), '-y', '-hide_banner', '-loglevel', 'warning']
    for s in p.shots:
        cmd += ['-ss', str(s.in_seconds), '-t', str(s.duration), '-i', str(p.resolve(s.source))]
    n = len(p.shots)
    ni = mi = None
    if p.narration:
        ni = n
        n += 1
        cmd += ['-i', str(p.resolve(p.narration))]
    if p.music:
        mi = n
        cmd += ['-i', str(p.resolve(p.music))]
    g, a = build_filtergraph(p, ni, mi)
    if preview:
        g = g.replace(f'scale={p.width}:{p.height}', 'scale=540:960')
    cmd += ['-filter_complex_script', '__GRAPH__', '-filter_threads', '2', '-filter_complex_threads', '2', '-map', '[vout]'] + (['-map', '[aout]'] if a else []) + ['-t', str(p.duration), '-r', str(p.fps), '-c:v', 'libx264', '-threads', '4', '-preset', 'veryfast' if preview else 'fast', '-crf', '23' if preview else '18', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-level', '4.1']
    if a:
        cmd += ['-c:a', 'aac', '-b:a', '192k', '-ar', '48000']
    cmd += ['-movflags', '+faststart', '-metadata', f'title={p.title}', '-metadata', 'comment=Hybrid Premium draft_only', str(out)]
    return cmd, g

def sha(p):
    h = hashlib.sha256()
    h.update(Path(p).read_bytes())
    return h.hexdigest()

def render(p: EditPlan, out, preview=False):
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd, g = build_command(p, out, preview)
    with tempfile.NamedTemporaryFile('w', suffix='.ffgraph', delete=False) as f:
        f.write(g)
        gp = f.name
    cmd[cmd.index('__GRAPH__')] = gp
    try:
        subprocess.run(cmd, cwd=p.base_dir, check=True)
    finally:
        Path(gp).unlink(missing_ok=True)
    m = {
        'schema_version': 1,
        'plan': str(p.path),
        'plan_sha256': sha(p.path),
        'output': str(out),
        'output_sha256': sha(out),
        'bytes': out.stat().st_size,
        'duration': p.duration,
        'resolution': [540, 960] if preview else [p.width, p.height],
        'fps': p.fps,
        'visual_beats': len(p.shots),
        'preview': preview,
        'rendered_at': datetime.now(timezone.utc).isoformat(),
        'draft_only': True
    }
    out.with_suffix('.manifest.json').write_text(json.dumps(m, indent=2))
    return out
