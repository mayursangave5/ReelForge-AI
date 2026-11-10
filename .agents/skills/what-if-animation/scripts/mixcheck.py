"""Step 7 check: is the voice clear of the effects and the music? Measures the three stems at their mix volumes in
0.4 s windows and lists the moments, while someone is speaking, where effects or music come within `margin` dB of the
voice. Fix a flagged moment by lowering that event's gain in episode.json, then re-run sfx.py.

python <skill>/scripts/mixcheck.py <slug> [--margin 3]
"""
import json, sys

import numpy as np

from wi import SR, decode, ep_dir, stem

slug = sys.argv[1]
margin = float(sys.argv[sys.argv.index('--margin') + 1]) if '--margin' in sys.argv else 3.0
tl = json.loads((ep_dir(slug) / 'timeline.json').read_text(encoding='utf-8'))
A = tl['audio']
stems = {k: decode(stem(slug, k)) * A.get(f'{k}Vol', 1) for k in ['voice', 'sfx', 'music'] if stem(slug, k)}
n = min(len(x) for x in stems.values())
W = int(0.4 * SR)


def db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)


segs = tl['segments']
starts = range(0, n - W, W // 2)
levels = [db(stems['voice'][i:i + W]) for i in starts]
speaking = float(np.percentile([v for v in levels if v > -60], 70)) - 8  # windows this loud are words, not pauses
flags = []
for i, v in zip(starts, levels):
    if v < speaking:
        continue
    for k in ['sfx', 'music']:
        if k in stems:
            o = db(stems[k][i:i + W])
            if o > v - margin:
                fr = int(i / SR * tl['fps'])
                shot = next((s['shot'] for s in segs if s['a'] <= fr < s['b']), '?')
                flags.append((round(i / SR, 1), shot, k, round(o - v, 1)))
mix = sum(x[:n] for x in stems.values())
print(f'{len(flags)} moments where the effects or music come within {margin:g} dB of the voice (time s, shot, stem, dB over the voice):')
for f in flags:
    print('  ', f)
print('mix peak before mastering:', round(float(np.abs(mix).max()), 3))
