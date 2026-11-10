"""Step 3: the shot list on the voice. Resolves the edit's cues against the word timings and writes the timeline.

python <skill>/scripts/plan.py <slug>
Reads  src/episodes/<slug>/episode.json (shots, edit, fx) and words.json (from voice.py)
Writes src/episodes/<slug>/timeline.json (the engine reads it) and out/<slug>/shotlist.md, and prints the pace.

An edit entry:  {"shot": "S4", "at": "homework", "look": "copy"}
  at       when the cut lands: a word ("homework", "paste#2" = its 2nd occurrence after the previous cut), "+18" (frames
           after the previous cut), "s:4.2", "f:126". A word cut lands `lead` frames (default 2) before the word.
  reverse  true plays the shot's clock backwards, from where it was last seen ("from") to "to" (default 0)
  from     the shot's clock at the cut (default 0 forward)
  look     a power look the episode defines (rewind, copy...): grade and overlay while it runs
The episode ends `tail` seconds (default 0.9) after the last word, or at "end": "<cue>".
"""
import statistics, sys

from wi import ep_dir, load_episode, load_json, out_dir, resolve, save_json, find_word, stem

slug = sys.argv[1]
ep = load_episode(slug)
FPS = ep.get('fps', 30)
LEAD = ep.get('lead', 2)
words = load_json(ep_dir(slug) / 'words.json', [])
if not words and any(not str(e['at']).startswith(('f:', 's:', '+')) for e in ep['edit']):
    raise SystemExit('No words.json yet: run voice.py first (or use f:/s: cues).')
shots = {s['id']: s for s in ep['shots']}

# ---------------------------------------------------------------- cut points
starts, wi_prev, prev = [], 0, 0
for k, e in enumerate(ep['edit']):
    if e['shot'] not in shots:
        raise SystemExit(f'Edit entry {k} uses unknown shot {e["shot"]}')
    at = str(e['at'])
    if at.startswith(('f:', 's:')):
        a = resolve(at, words, FPS)
    elif at.startswith('+'):
        a = prev + int(at[1:])
    else:
        base, _, off = at.partition('+') if '+' in at else (at, '', '0')
        if '#' in base:
            w, n = base.split('#')
            i = find_word(words, w, wi_prev, int(n))
        else:
            i = find_word(words, base, wi_prev)
        wi_prev = i + 1
        a = max(0, round(words[i]['s'] * FPS) - LEAD + int(off or 0))
    if k == 0:
        a = 0
    if a <= prev and k > 0:
        raise SystemExit(f'Edit entry {k} ({e["shot"]} at {at}) starts at frame {a}, not after the previous cut ({prev})')
    starts.append(a)
    prev = a
end = resolve(ep['end'], words, FPS) if 'end' in ep else round((words[-1]['e'] + ep.get('tail', 0.9)) * FPS)
if end <= starts[-1]:
    raise SystemExit(f'The last shot starts at {starts[-1]} but the episode ends at {end}')

# ---------------------------------------------------------------- segments and shot clocks
segments, last_clock = [], {}
for k, e in enumerate(ep['edit']):
    a, b = starts[k], starts[k + 1] if k + 1 < len(starts) else end
    if e.get('reverse'):
        t0 = e.get('from', last_clock.get(e['shot'], b - a))
        t1 = e.get('to', 0)
    else:
        t0 = e.get('from', 0)
        t1 = t0 + (b - a)
    last_clock[e['shot']] = t1
    line = ' '.join(w['w'] + w.get('p', '').strip() for w in words if a <= round(w['s'] * FPS) + LEAD < b)
    seg = {'shot': e['shot'], 'a': a, 'b': b, 't0': t0, 't1': t1, 'line': line}
    if e.get('look'):
        seg['look'] = e['look']
    segments.append(seg)

ids = list(dict.fromkeys(s['shot'] for s in segments))
for sid in shots:
    if sid not in ids:
        print(f'note: shot {sid} is defined but not in the edit')
info = []
for sid in ids:
    segs = [s for s in segments if s['shot'] == sid]
    fwd = [s for s in segs if s['t1'] >= s['t0']]
    length = max([s['t1'] for s in fwd] + [s['t0'] for s in segs])
    d = shots[sid]
    first = segs[0]
    info.append({
        'id': sid, 'size': d.get('size', ''), 'key': d.get('key', (first['b'] - first['a']) // 2), 'len': length, 'first': first['a'],
        'line': first['line'], 'note': d.get('note', ''),
    })

# ---------------------------------------------------------------- fx, audio
fx = []
for e in ep.get('fx', []):
    item = {k: v for k, v in e.items() if k != 'at'}
    item['f'] = resolve(e['at'], words, FPS, segments, ids)
    fx.append(item)
old = load_json(ep_dir(slug) / 'timeline.json', {}) or {}
audio = {k: v for k, v in old.get('audio', {}).items() if k.endswith('Vol')}
for k in ['voice', 'sfx', 'music']:
    f = stem(slug, k)
    if f:
        audio[k] = f'{slug}/{f.name}'
title = ep.get('title', ['', ''])
tl = {'slug': slug, 'title': ' '.join(title) if isinstance(title, list) else title, 'fps': FPS, 'total': end, 'segments': segments, 'shots': info, 'fx': fx, 'audio': audio}
save_json(ep_dir(slug) / 'timeline.json', tl)

# ---------------------------------------------------------------- the pace report and the shot list
cuts = [s['a'] for s in segments[1:]]
lens = [(s['b'] - s['a']) / FPS for s in segments]
dur = end / FPS
first10 = len([c for c in cuts if c < 10 * FPS])
per_min = len(cuts) / dur * 60
print(f'{len(segments)} segments, {len(ids)} shots, {dur:.1f} s ({end} frames)')
print(f'pace: {per_min:.0f} cuts/min overall, {first10 / min(10, dur) * 60:.0f} cuts/min in the first 10 s; median shot {statistics.median(lens):.1f} s, longest {max(lens):.1f} s')
if per_min < 24:
    print('  ! slower than the genre opening (about 27 cuts a minute): split long shots or cut on more words')
for s in segments:
    if (s['b'] - s['a']) / FPS > 4:
        print(f'  ! {s["shot"]} holds {(s["b"] - s["a"]) / FPS:.1f} s: give it action inside (a move, a light change, a push in) or split it')
rows = ['| # | Shot | Size | In | Length | Clock | Look | Words |', '|---|---|---|---|---|---|---|---|']
for k, s in enumerate(segments):
    d = shots[s['shot']]
    clock = f"{s['t0']:.0f}→{s['t1']:.0f}" + (' (back)' if s['t1'] < s['t0'] else '')
    rows.append(f"| {k + 1} | {s['shot']} | {d.get('size', '')} | {s['a'] / FPS:.2f} s | {(s['b'] - s['a']) / FPS:.2f} s | {clock} | {s.get('look', '')} | {s['line']} |")
md = f"# {tl['title']}: shot list\n\n{dur:.1f} s, {len(segments)} segments, {per_min:.0f} cuts/min\n\n" + '\n'.join(rows) + '\n'
(out_dir(slug) / 'shotlist.md').write_text(md, encoding='utf-8')
print(md)
