"""Step 4: the storyboard sheet. Lays the board stills out as one captioned contact sheet: shot number and size, start
time, the words over it, and the note. This is what gets reviewed (by you, then by the person) before any animation.

python <skill>/scripts/board.py <slug> [--cols 3]
Reads  out/<slug>/board/<shot>.png (from stills.mjs) and src/episodes/<slug>/timeline.json
Writes out/<slug>/storyboard.jpg
"""
import json, pathlib, sys

from PIL import Image, ImageDraw, ImageFont

from wi import STUDIO, ep_dir, out_dir

slug = sys.argv[1]
cols = int(sys.argv[sys.argv.index('--cols') + 1]) if '--cols' in sys.argv else 3
tl = json.loads((ep_dir(slug) / 'timeline.json').read_text(encoding='utf-8'))
ep = json.loads((ep_dir(slug) / 'episode.json').read_text(encoding='utf-8'))
src = out_dir(slug) / 'board'


def font(size, bold=True):
    """The first face that exists: your own (fonts/ in the studio), then common system faces, then Pillow's default."""
    cands = [STUDIO / 'public' / 'fonts' / 'board.ttf', STUDIO / 'public' / 'fonts' / 'board.otf']
    cands += [pathlib.Path(p) for p in ['C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/arialbd.ttf',
                                         '/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/System/Library/Fonts/Helvetica.ttc',
                                         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']]
    for c in cands:
        if c.exists():
            return ImageFont.truetype(str(c), size)
    return ImageFont.load_default(size)


head, body, note = font(34), font(28), font(23, False)
W, H, CAP, PAD = 960, 540, 160, 24
n = len(tl['shots'])
rows = (n + cols - 1) // cols
sheet = Image.new('RGB', (cols * W + (cols + 1) * PAD, rows * (H + CAP + PAD) + PAD + 90), (20, 17, 26))
d = ImageDraw.Draw(sheet)
title = ' '.join(ep['title']) if isinstance(ep.get('title'), list) else ep.get('topic', slug)
d.text((PAD, 26), f'{title}  ·  storyboard, one key frame per shot  ·  {tl["total"] / tl["fps"]:.1f} s', font=head, fill=(246, 239, 227))


def fit(text, f, width):
    """Wrap text into at most two lines that fit the caption."""
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1][: max(0, len(lines[1]) - 2)] + '…'
    return lines


for i, s in enumerate(tl['shots']):
    x = PAD + (i % cols) * (W + PAD)
    y = 90 + PAD + (i // cols) * (H + CAP + PAD)
    p = src / f'{s["id"]}.png'
    if p.exists():
        sheet.paste(Image.open(p).convert('RGB').resize((W, H)), (x, y))
    else:
        d.rectangle([x, y, x + W, y + H], fill=(60, 30, 40))
        d.text((x + 20, y + 20), f'missing {p.name}', font=body, fill=(255, 120, 120))
    d.rectangle([x, y + H, x + W, y + H + CAP], fill=(32, 27, 40))
    d.text((x + 18, y + H + 12), f'{i + 1}  {s["id"]}  {s["size"].upper()}', font=head, fill=(255, 177, 90))
    at = f'{s["first"] / tl["fps"]:.1f} s'
    d.text((x + W - 18 - d.textlength(at, font=note), y + H + 20), at, font=note, fill=(170, 160, 185))
    line = f'"{s["line"]}"' if s.get('line') else '(no words)'
    yy = y + H + 58
    for ln in fit(line, body, W - 36):
        d.text((x + 18, yy), ln, font=body, fill=(246, 239, 227))
        yy += 34
    if s.get('note'):
        d.text((x + 18, yy + 2), fit(s['note'], note, W - 36)[0], font=note, fill=(170, 160, 185))
out = out_dir(slug) / 'storyboard.jpg'
sheet.save(out, quality=88)
print(out, sheet.size)
