"""Shared helpers for the What If animation scripts: paths, the API key, credits, cues, audio files.

Every script runs from the studio folder (the copy of studio/ where you ran npm install) and takes the episode slug:
    python <skill>/scripts/plan.py copy-paste
Episode files:  src/episodes/<slug>/episode.json (you write it), words.json + timeline.json (the scripts write them)
Audio:          public/<slug>/voice.wav, sfx.wav, music.wav
Renders/review: out/<slug>/
Sound library:  library/sfx/ (generated clips, cached by name + prompt + length, shared by every episode)
"""
import hashlib, json, os, pathlib, re, subprocess, sys, time, urllib.request, wave

import numpy as np

SR = 44100
sys.stdout.reconfigure(encoding='utf-8')
STUDIO = pathlib.Path.cwd()
if not (STUDIO / 'src' / 'episodes').exists():
    raise SystemExit('Run this from the studio folder (the one with src/episodes and package.json).')
LIB = STUDIO / 'library' / 'sfx'


# ---------------------------------------------------------------- paths
def ep_dir(slug):
    return STUDIO / 'src' / 'episodes' / slug


def pub_dir(slug):
    d = STUDIO / 'public' / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def out_dir(slug):
    d = STUDIO / 'out' / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def stem(slug, name):
    """An audio stem in public/<slug>/: name.wav, or name.mp3 (the shipped examples), or None."""
    for ext in ('wav', 'mp3'):
        q = STUDIO / 'public' / slug / f'{name}.{ext}'
        if q.exists():
            return q
    return None


def load_episode(slug):
    p = ep_dir(slug) / 'episode.json'
    if not p.exists():
        raise SystemExit(f'No episode.json at {p}')
    return json.loads(p.read_text(encoding='utf-8'))


def load_json(p, default=None):
    p = pathlib.Path(p)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default


def save_json(p, data):
    pathlib.Path(p).write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')


# ---------------------------------------------------------------- the key and credits
KEY_NAMES = ['ELEVENLABS_API_KEY']


def read_env(p):
    """A .env as text, however it was saved: UTF-8 with or without a BOM, or UTF-16 (Windows PowerShell's `>`)."""
    raw = p.read_bytes()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return raw.decode('utf-16', errors='ignore')
    return raw.decode('utf-8-sig', errors='ignore')


def api_key():
    """The ElevenLabs key, by name only: from the environment, or the nearest .env above the studio. Never printed."""
    for n in KEY_NAMES:
        if os.environ.get(n):
            return os.environ[n]
    for d in [STUDIO, *STUDIO.parents]:
        p = d / '.env'
        if p.exists():
            for line in read_env(p).splitlines():
                for n in KEY_NAMES:
                    if line.strip().startswith(n + '='):
                        return line.split('=', 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f'No ElevenLabs key: set one of {KEY_NAMES} in the environment or a .env file.')


def api(path, body=None, timeout=180):
    req = urllib.request.Request('https://api.elevenlabs.io' + path, headers={'xi-api-key': api_key(), 'Content-Type': 'application/json'})
    if body is not None:
        req.data = json.dumps(body).encode()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def credits_used():
    """Characters/credits used so far this billing period (ElevenLabs' counter; it can lag by minutes)."""
    s = json.loads(api('/v1/user/subscription'))
    return s['character_count'], s['character_limit']


def spent_since(t0, expect=1, tries=6):
    """Credits spent since unix time t0, read from the account's generation history, which records each item's exact
    cost (the subscription counter lags). Waits a little for `expect` items to appear. Returns (credits, items)."""
    items = []
    for i in range(tries):
        h = json.loads(api('/v1/history?page_size=100'))
        items = [it for it in h.get('history', []) if it.get('date_unix', 0) >= int(t0) - 2]
        if len(items) >= expect:
            break
        time.sleep(2 + 2 * i)
    used = sum((it.get('character_count_change_to') or 0) - (it.get('character_count_change_from') or 0) for it in items)
    return used, len(items)


def log_cost(slug, step, used, note=''):
    """Append a cost line to out/<slug>/costs.json and print the running total for the episode."""
    p = out_dir(slug) / 'costs.json'
    rows = load_json(p, [])
    rows.append({'step': step, 'credits': used, 'note': note})
    save_json(p, rows)
    total = sum(r['credits'] for r in rows)
    print(f'ElevenLabs: {step} used {used} credits{f" ({note})" if note else ""}; this episode so far: {total}')


# ---------------------------------------------------------------- words and cues
def norm(w):
    return re.sub(r"[^\w']", '', w.lower().replace('’', "'"))


def word_frame(words, fps, i):
    return round(words[i]['s'] * fps)


def find_word(words, target, start=0, nth=1):
    t = norm(target)
    seen = 0
    for i in range(start, len(words)):
        if norm(words[i]['w']) == t:
            seen += 1
            if seen == nth:
                return i
    raise SystemExit(f'Cue word "{target}" (#{nth}) not found after word {start}. Words: ' + ' '.join(w['w'] for w in words))


CUE = re.compile(r'^(?P<base>[^+\-#]+?)(?:#(?P<nth>\d+))?(?P<off>[+-]\d+)?$')


def resolve(cue, words, fps, segments=None, shot_ids=()):
    """A cue to a global frame. Forms:
    f:123      an absolute frame          s:4.2     seconds
    S3+2       2 frames after the start of shot S3's first segment (S3#2+2: its second segment; S3-4 before it)
    word+3     3 frames after the word starts (word#2: its second occurrence)
    """
    cue = str(cue).strip()
    if cue.startswith('f:'):
        return int(round(float(cue[2:])))
    if cue.startswith('s:'):
        return int(round(float(cue[2:]) * fps))
    m = CUE.match(cue)
    if not m:
        raise SystemExit(f'Bad cue "{cue}"')
    base, nth, off = m['base'], int(m['nth'] or 1), int(m['off'] or 0)
    if segments is not None and base in shot_ids:
        segs = [s for s in segments if s['shot'] == base]
        if len(segs) < nth:
            raise SystemExit(f'Cue "{cue}": shot {base} has only {len(segs)} segment(s)')
        return segs[nth - 1]['a'] + off
    return word_frame(words, fps, find_word(words, base, 0, nth)) + off


# ---------------------------------------------------------------- audio
def decode(path):
    """Any audio file to mono float64 at 44.1 kHz."""
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def write_wav(path, x, peak=None):
    if peak is not None:
        x = x / max(1e-9, np.abs(x).max()) * peak
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def loudness(path_or_args):
    """Integrated loudness (LUFS) and true peak (dBTP) of a file, via ffmpeg's ebur128."""
    args = path_or_args if isinstance(path_or_args, list) else ['-i', str(path_or_args)]
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *args, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
    txt = r.stderr
    summ = txt[txt.rfind('Summary:'):]
    i = re.search(r'I:\s+(-?[\d.]+|-inf) LUFS', summ)
    p = re.search(r'Peak:\s+(-?[\d.]+|-inf) dBFS', summ)
    f = lambda m: float(m.group(1)) if m and m.group(1) != '-inf' else float('-inf')
    return f(i), f(p)


def clip_path(name, prompt, secs):
    h = hashlib.sha1(f'{prompt}|{secs}'.encode()).hexdigest()[:8]
    LIB.mkdir(parents=True, exist_ok=True)
    return LIB / f'{name}-{h}.mp3'
