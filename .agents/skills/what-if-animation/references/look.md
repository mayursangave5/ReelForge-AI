# The look: what the genre does, and the self-check

Measured on 21 Oct 2026, frame by frame, from the leading channel's most-viewed episode (4.2M views, 24 fps) with
ffmpeg scene detection. We learn the technique (timing, camera grammar, light); every character, set and story stays
our own. Nothing confirms how the viral channels make their videos, so never say or imply they're made with Claude
or any other tool.

## Pace

| | The genre | Our target for 15-25 s |
|---|---|---|
| Cuts per minute, opening | about 27 (first 90 s) | 27 or more; the cold open can run 40-70 with reversals |
| Median shot | 2.7 s in the opening | 0.7 to 3 s |
| Long holds | up to about 12 s, always with action inside | nothing static over about 3 s |

- Cuts come from **changing shot size**, not from motion: wide, then a macro insert, then a medium, then a close-up
  of a hand, then a reaction. No two neighbouring shots share a size and angle.
- The opening runs about twice as fast as the rest. Cut on the word: `plan.py` lands each cut 2 frames before its
  cue word.

## Light does most of the work

- A dusk palette: purple to orange sky, a low sun with soft rays behind the subject.
- **Every light comes from something you can see:** a window with the sun in it, a pendant, a wall light, a desk
  lamp, string lights, a lit doorway, city windows. Pools of light, dark corners.
- Muted, mid-dark walls (`S3` palette), so the practicals read; then `LightVeil` sinks the mid-tones further and
  leaves holes where the light falls.
- A warm rim light on every character edge, on the side facing the light (`rimId="rimR"` or `"rimL"`;
  `"rimRed"` for the turn).
- Haze, dust in the beams (`Dust`), soft bokeh. Depth of field: foreground objects blurred dark (`Foreground`),
  the middle sharp, the background soft on close-ups (`blur16` on a scaled-up set).
- Grain on twos and a soft vignette finish the frame (the engine's `Grade`).

## Shot vocabulary

- **Establishing wide:** the whole lit room, the character small in it.
- **Medium** (waist up, camera zoom about 1.6 to 2) and **close-up** (head; 3 to 4.5 for an extreme close-up).
- **Macro insert:** an object huge in frame, shallow focus (a mug, a cookie, a hand), often a high or top-down angle.
- **Over the shoulder:** a big, dark, blurred foreground figure filling a third of the frame.
- **High angle / top-down** (looking down at a desk, a landing) and **low angle** (looking up at a character against
  the sky: the rooftop's `low` prop).
- **Schematic** for the science beat: a dark grid, line icons, labels in the mono face, numbers counting.
- **Title card:** a wide establishing shot with the title over it, small first line, big second line.

## Characters

- Mostly three-quarter or profile (`yaw`), rarely face-on; the face slides toward the side they face.
- They animate very little: holds are near-still, with small hand changes. Expressions swap instantly through a
  blink (`faceAt`), never morph.
- Life comes from around them: a one-frame flash on an impact, focus rings, a timer, floating labels, dust, steam,
  a swaying lamp, a slow push-in.
- One hero who never changes. Every costume is a `Look` on the one rig, so it can't drift.

## On-screen text

Almost none. The title card, and small UI readouts in the mono face (a timer, a chip naming the power, a short
label). No speech bubbles, no "HA HA", no captions of the voice.

## The storyboard self-check (step 5)

Look at `storyboard.jpg`, then open every still at full size. Fix anything that fails, re-render those shots, look
again. Only a board that passes goes to animation.

1. **One read in a second.** At phone size the subject and the action are clear. If it needs the voice to make
   sense, reframe it.
2. **Sizes change.** No two neighbours share a size and angle; the board has wides, inserts, mediums, close-ups and
   at least one high or low angle.
3. **Light from a source.** Every shot has a visible practical or sunlight, and the subject sits in or against a
   pool of it. Mid-tones are dark; nothing is evenly lit.
4. **The character pops.** The face is the brightest, sharpest thing in its area; the rim light is on the lit side;
   no dark limb on a dark wall.
5. **Depth.** A blurred dark foreground in about a third of the shots; soft backgrounds on close-ups.
6. **The world is full.** Wides show 20 or more designed objects; no empty wall, no floating furniture. Everything
   that stands has legs and a contact shadow.
7. **Perspective holds.** Objects sit on their surfaces, at the right scale for the character, toward the room's
   vanishing point.
8. **Acting matches the line.** The expression and pose say the line without the voice; the hand that moves is the
   near one (with `yaw < 0` the far arm hides behind the body).
9. **Continuity.** Same costume, same set layout, same props in the same places across shots of one place.
10. **Only the title and readouts as text,** spelled right, inside the frame.
11. **Ours.** Nothing resembles a famous character, a channel's hero or a brand.

## The motion check (step 6)

Pull frame grids of every action shot with `motiongrid.py` and read them like a flipbook.

- Anticipation before a big move (a crouch before a step, a wind-up before a grab), a hold of 2 frames on the beat
  where the character realises, overshoot and settle on landings and catches.
- Nothing static for more than about a second: something always moves (dust, steam, a sway, a push-in).
- The action lands on its word, within about 3 frames.
- Reversals read backwards (every move derives from `t`, so it does).
- No pops: a prop never jumps between frames unless it's meant to (a paste, a flash).
