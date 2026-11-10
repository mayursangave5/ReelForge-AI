# Sound

The genre is dense with sound: every visible action has its own effect, ambience fills every gap, a light music bed
runs under the cold open and cuts out at the turn. All of it comes from ElevenLabs' sound generation, cached in
`library/sfx/`, so a clip is paid for once and reused by every later episode.

## Writing the events

One event per visible action, cued to the shot it happens in, so retiming the voice never breaks the sync:

```json
"events": [
  ["S2+6", "glass_tink", 0.5],                    cue, clip, gain (0..1, clips are peak-levelled first)
  ["S3+2", "whoosh", 0.4, "peak"],                "peak": the clip's loudest moment lands on the cue (whooshes, booms)
  ["S1", "kitchen_tone", 0.12, "onset", "S6"],    an ambience from S1 cut (with a fade) where S6 starts
  ["paste+2", "pop", 0.5]                         or cue on a word
]
```

- **A hit that illustrates a word lands in the pause after it, never on it.** The copy-paste run first put each
  paste's pop on the word "Paste" and covered it; moved four to six frames later, into the gap, the word reads and
  the pop lands as the answer to it. Move the picture with it (the copy appears with its sound).
- **Align by the attack, not the file start:** `onset` (default) finds where the clip actually starts sounding. A hit
  on the frame of the visible impact; a whoosh with `peak` on the frame of the fastest movement.
- **Layers for each beat:** the action (a step, a catch), the power (its signature sound every time it's used), the
  reaction (a laugh, a gasp, a sparkle), and the room (an ambience per location, cut at the location change).
- **The power's sound** is the episode's signature: the same clip every time, so the viewer hears the rule.
- **The turn** gets a low hit (drone or boom) on its first frame, the music cut on the same frame, and one detail
  sound repeated (bulbs dying, lights switching off) through `repeats`.
- **Silence is a tool:** cut the music a beat before the title boom or the turn so the hit lands in a gap.

## Prompts that work

Describe the physical source, the material and the length: "a ceramic coffee mug smashing on a wooden floor, shards
scattering and liquid splash" beats "smash sound". Add "cartoon" for exaggerated comedy sounds (a tiptoe, dizzy
birds), "short" for one-shots, "no voices" for ambiences. Durations: 0.5 to 1.6 s for hits, 2 to 12 s for
ambiences, the episode's length for the music bed ("playful quirky cartoon background music, pizzicato strings,
glockenspiel and soft bass, light and curious, 110 bpm, no vocals").

Check the library first (`python <skill>/scripts/sfx.py <slug> --dry` lists what's cached): reuse a clip by giving
it the same name, prompt and length.

## Levels

`sfx.py` measures the voice and each stem and sets their volumes in the mix:

- effects stem: `sfx_lu` LU against the voice, integrated. The default, +1.5, is about where the approved proof clip
  sat (+1.9); the copy-paste run settled at -1.5 after the mix check. The stem is sparse, so its gated loudness reads
  high: these numbers sound denser than they look.
- music bed: `music_lu` (default -9.5) LU against the voice.
- The whole effects stem is levelled to `sfx_lu`, so lowering one event's gain makes the others louder. Lower events
  to change the balance inside the stem; lower `sfx_lu` to give the voice more room overall.
- The final mix is brought to -14 LUFS with true peaks under -1 dBTP by `master.py`.

Then run `mixcheck.py`: it lists the spoken moments where effects or music come within 3 dB of the voice. Fix the
words that matter (the fact, the last line) by moving a hit into the pause after the word or lowering it; a title
boom or a drone on the turn can stay. The proof clip had 30 such moments at 0 dB; copy-paste shipped with 14.

## Costs

The voice's exact cost is in the account's generation history, which `voice.py` reads: the 356-character copy-paste
take cost 78 credits (about 0.22 a character on this account; the proof clip's 280-character takes cost 61 and 62).
By 29 Oct 2026 the same voice and model cost about 0.44 a character (the 358-character preview-minute take: 158), so
count the characters and re-check the rate before the call.
Sound clips don't appear in the history, so `sfx.py` reads the account counter before and after, and the counter can
lag: re-read it before you report a number, or check the usage page. The copy-paste run's 12 new clips (13.5 s in
all) moved the counter by 74 credits. The proof clip's sound cost more (775 credits for five clips including 19 s of
ambience), so long ambiences are where the cost is: reuse `room_tone` and `roof_wind` from the library.
